"""Local-first recommendation API. Configure ATLAS_API_KEY before public exposure."""

import json
import logging
import os
import secrets
import time
import uuid
from collections import defaultdict, deque
from threading import Lock
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, Field

from atlas.registry import Registry
from atlas.storage import Store

logger = logging.getLogger("atlas.requests")


class RecommendRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    k: int = Field(default=10, ge=1, le=50)
    candidate_count: int = Field(default=100, ge=50, le=1000)
    algorithm: Literal[
        "auto", "popularity", "category_popularity", "als", "content", "tower", "ranked"
    ] = "auto"
    preferred_categories: list[str] = Field(default_factory=list, max_length=10)
    category_filter: str | None = Field(default=None, max_length=100)
    source: Literal["demo", "organic", "load_test"] = "demo"


class FeedbackRequest(BaseModel):
    event_id: str = Field(min_length=1, max_length=128)
    request_id: str = Field(min_length=1, max_length=128)
    item_id: str = Field(min_length=1, max_length=128)
    signal: Literal["like", "dislike", "click"]


def create_app(state_path=None, db_path=None, api_key=None, allow_faults=False):
    registry = Registry(state_path or os.getenv("ATLAS_STATE", "artifacts/registry.json"))
    store = Store(db_path or os.getenv("ATLAS_DB", "artifacts/feedback.sqlite"))
    expected_key = api_key if api_key is not None else os.getenv("ATLAS_API_KEY", "")
    app = FastAPI(
        title="Atlas",
        version="0.1.0",
        description="Recommendation engineering lab",
        root_path=os.getenv("ATLAS_ROOT_PATH", ""),
    )
    app.state.registry, app.state.store = registry, store
    app.state.faults = {}  # Test harness only; no fault-injection HTTP endpoint.
    prom = CollectorRegistry()
    requests = Counter(
        "atlas_requests_total", "Recommendation requests", ["slot", "algorithm"], registry=prom
    )
    fallback = Counter("atlas_fallback_total", "Fallback responses", ["reason"], registry=prom)
    errors = Counter("atlas_errors_total", "Unexpected recommendation errors", registry=prom)
    latency = Histogram(
        "atlas_request_seconds",
        "Total recommendation latency",
        ["slot"],
        registry=prom,
        buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.15, 0.25, 0.5, 1),
    )
    retrieval_latency = Histogram("atlas_retrieval_seconds", "Retrieval latency", registry=prom)
    ranking_latency = Histogram("atlas_ranking_seconds", "Ranking latency", registry=prom)
    missing = Counter(
        "atlas_unknown_category_total", "Unknown onboarding categories", registry=prom
    )
    active = Gauge("atlas_active_model", "Loaded model bundle", ["version", "slot"], registry=prom)
    rate_lock, arrivals = Lock(), defaultdict(deque)

    def authorize(request: Request, x_api_key: str | None = Header(default=None)):
        if expected_key and (
            x_api_key is None or not secrets.compare_digest(x_api_key, expected_key)
        ):
            raise HTTPException(401, "Invalid API key")
        peer = request.client.host if request.client else "local"
        now = time.monotonic()
        with rate_lock:
            q = arrivals[peer]
            while q and q[0] < now - 60:
                q.popleft()
            if len(q) >= 6000:
                raise HTTPException(429, "Request rate exceeded")
            q.append(now)
            if len(arrivals) > 10000:
                for old in list(arrivals):
                    if not arrivals[old] or arrivals[old][-1] < now - 60:
                        del arrivals[old]

    @app.get("/health")
    def health():
        return {"status": "alive"}

    @app.get("/ready")
    def ready():
        registry.reload()
        primary = registry.bundles[registry.state["primary"]]
        return {
            "status": "ready",
            "version": primary.version,
            "synthetic": primary.manifest["dataset"]["synthetic"],
        }

    @app.post("/recommend", dependencies=[Depends(authorize)])
    def recommend(body: RecommendRequest):
        start = time.perf_counter()
        bundle, slot = registry.select(body.user_id)
        state = bundle.histories.get(body.user_id, {"positive": [], "seen": []})
        history, seen = list(state["positive"]), list(state["seen"])
        onboarding = False
        if not history and body.preferred_categories:
            for category in body.preferred_categories:
                matches = [i for i, item in enumerate(bundle.items) if item["category"] == category]
                if matches:
                    history.append(matches[0])
                    onboarding = True
                else:
                    missing.inc()
        algorithm = (
            bundle.manifest["default_algorithm"] if body.algorithm == "auto" else body.algorithm
        )
        reason = None
        try:
            if allow_faults:
                delay = app.state.faults.get(slot, {}).get("delay_ms", 0)
                if delay:
                    time.sleep(delay / 1000)
                if app.state.faults.get(slot, {}).get("retrieval_error"):
                    raise RuntimeError("Injected retrieval failure")
            ids, scores, reason, timing = bundle.candidates(
                history, seen, body.candidate_count, algorithm, category=body.category_filter
            )
            # Deadline detection cannot preempt a running FAISS call; report this limitation.
            if (time.perf_counter() - start) * 1000 > 150 and algorithm not in (
                "popularity",
                "category_popularity",
            ):
                ids, scores, _, timing = bundle.candidates(
                    history, seen, body.candidate_count, "popularity", category=body.category_filter
                )
                reason = "retrieval_deadline_exceeded"
        except (RuntimeError, ValueError):
            errors.inc()
            ids, scores, _, timing = bundle.candidates(
                history, seen, body.candidate_count, "popularity", category=body.category_filter
            )
            reason = "retrieval_failure"
        request_id = str(uuid.uuid4())
        effective_algorithm = (
            "popularity"
            if reason in {"no_positive_history", "retrieval_failure", "retrieval_deadline_exceeded"}
            else "tower"
            if reason == "ranker_unavailable"
            else "content"
            if reason == "als_no_signal"
            else algorithm
        )
        recommendations = [
            {
                "item_id": bundle.items[int(i)]["item_id"],
                "title": bundle.items[int(i)]["title"],
                "rank": r + 1,
                "score": float(score),
                "diagnostics": bundle.explain(int(i), history),
            }
            for r, (i, score) in enumerate(zip(ids[: body.k], scores[: body.k], strict=True))
        ]
        store.exposure(
            request_id,
            body.user_id,
            body.source,
            bundle.version,
            slot,
            [x["item_id"] for x in recommendations],
        )
        elapsed = time.perf_counter() - start
        requests.labels(slot, algorithm).inc()
        if reason:
            fallback.labels(reason).inc()
        latency.labels(slot).observe(elapsed)
        retrieval_latency.observe(timing["retrieval_ms"] / 1000)
        ranking_latency.observe(timing["ranking_ms"] / 1000)
        active.clear()
        for path, current in registry.bundles.items():
            active.labels(
                current.version, "primary" if path == registry.state["primary"] else "canary"
            ).set(1)
        result = {
            "request_id": request_id,
            "recommendations": recommendations,
            "model_version": bundle.version,
            "algorithm": algorithm,
            "effective_algorithm": effective_algorithm,
            "experiment_slot": slot,
            "fallback": reason is not None,
            "fallback_reason": reason,
            "onboarding_preferences_used": onboarding,
            "synthetic": bundle.manifest["dataset"]["synthetic"],
            "score_meaning": "Relative ranking signal, not a probability; fallback may change score scale",
            "processing_ms": elapsed * 1000,
            **timing,
        }
        logger.info(
            json.dumps(
                {
                    "request_id": request_id,
                    "version": bundle.version,
                    "slot": slot,
                    "algorithm": algorithm,
                    "processing_ms": result["processing_ms"],
                    "fallback_reason": reason,
                }
            )
        )
        return result

    @app.post("/feedback", dependencies=[Depends(authorize)])
    def feedback(body: FeedbackRequest):
        try:
            inserted = store.feedback(body.model_dump())
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"status": "recorded" if inserted else "duplicate", "event_id": body.event_id}

    @app.get("/metrics", dependencies=[Depends(authorize)])
    def metrics():
        return Response(generate_latest(prom), media_type="text/plain; version=0.0.4")

    return app
