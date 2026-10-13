"""Open-loop HTTP load test and isolated, reproducible canary regression demonstration."""

import asyncio
import json
import os
import platform
import shutil
import socket
import tempfile
import threading
import time
from pathlib import Path

import httpx
import numpy as np
from fastapi.testclient import TestClient

from atlas.api import create_app
from atlas.bundle import Bundle
from atlas.registry import activate, bucket, rollback


async def load_test(url, bundle_path, output, rate=50, duration=10, concurrency=32):
    bundle = Bundle(bundle_path)
    returning = [u for u, h in bundle.histories.items() if h["positive"]][:20]
    if not returning:
        returning = ["new-load-user"]
    headers = {"X-API-Key": os.getenv("ATLAS_API_KEY", "")}
    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
    records = []
    semaphore = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(
        base_url=url, headers=headers, timeout=30, limits=limits, trust_env=False
    ) as client:
        for i in range(30):
            response = await client.post(
                "/recommend",
                json={
                    "user_id": returning[i % len(returning)],
                    "source": "load_test",
                    "algorithm": "ranked",
                },
            )
            response.raise_for_status()
        start = time.perf_counter()

        async def one(i):
            arrival = start + i / rate
            await asyncio.sleep(max(0, arrival - time.perf_counter()))
            async with semaphore:
                dispatched = time.perf_counter()
                try:
                    response = await client.post(
                        "/recommend",
                        json={
                            "user_id": returning[i % len(returning)] if i % 5 else "new-load-user",
                            "source": "load_test",
                            "algorithm": "ranked",
                            "candidate_count": 100,
                        },
                    )
                    elapsed = time.perf_counter() - arrival
                    body = response.json() if response.status_code == 200 else {}
                    records.append(
                        {
                            "latency_ms": elapsed * 1000,
                            "status": response.status_code,
                            "dispatch_lag_ms": (dispatched - arrival) * 1000,
                            "fallback": body.get("fallback"),
                            "slot": body.get("experiment_slot"),
                            "processing_ms": body.get("processing_ms"),
                        }
                    )
                except httpx.HTTPError:
                    records.append(
                        {
                            "latency_ms": (time.perf_counter() - arrival) * 1000,
                            "status": 0,
                            "dispatch_lag_ms": (dispatched - arrival) * 1000,
                            "fallback": None,
                        }
                    )

        await asyncio.gather(*(one(i) for i in range(int(rate * duration))))
        wall = time.perf_counter() - start
    times = [r["latency_ms"] for r in records]
    successful = [r for r in records if r["status"] == 200]
    report = {
        "source": bundle.manifest["dataset"]["source"],
        "synthetic": bundle.manifest["dataset"]["synthetic"],
        "target_rps": rate,
        "requested_duration_seconds": duration,
        "wall_seconds": wall,
        "achieved_rps": len(successful) / wall,
        "requests": len(records),
        "warmup_requests": 30,
        "concurrency_limit": concurrency,
        "p50_ms": float(np.quantile(times, 0.5)),
        "p95_ms": float(np.quantile(times, 0.95)),
        "p99_ms": float(np.quantile(times, 0.99)),
        "error_rate": 1 - len(successful) / max(1, len(records)),
        "fallback_rate": sum(bool(r["fallback"]) for r in successful) / max(1, len(successful)),
        "p95_dispatch_lag_ms": float(np.quantile([r["dispatch_lag_ms"] for r in records], 0.95)),
        "catalog_size": len(bundle.items),
        "candidate_count": 100,
        "user_mix": "80% existing positive histories, 20% new user",
        "response_cache": "disabled; model/index arrays resident in RAM",
        "measurement": "Open-loop planned arrival to HTTP completion; includes queueing",
        "hardware": {
            "cpu_count": os.cpu_count(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python": platform.python_version(),
        },
        "target_met": len(successful) == len(records) and float(np.quantile(times, 0.95)) < 150,
        "limitations": "Local host, short run, one API worker; no fleet-scale conclusion",
    }
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(report, indent=2))
    return report


def canary_demo(bundle_path, output):
    parent = Path(output).parent / "canary_sandbox"
    if parent.exists():
        shutil.rmtree(parent)
    parent.mkdir(parents=True)
    candidate = parent / "candidate"
    shutil.copytree(bundle_path, candidate)
    manifest = json.loads((candidate / "bundle.json").read_text())
    manifest["version"] += "-candidate"
    (candidate / "bundle.json").write_text(json.dumps(manifest, indent=2))
    state = parent / "registry.json"
    activate(state, bundle_path)
    activate(state, candidate, canary_percent=25)
    app = create_app(state, parent / "feedback.sqlite", api_key="", allow_faults=True)
    app.state.faults["canary"] = {"delay_ms": 25, "retrieval_error": True}
    results = {"primary": [], "canary": []}
    with TestClient(app) as client:
        i = 0
        while min(len(v) for v in results.values()) < 20:
            user = f"rollout-user-{i}"
            slot = "canary" if bucket(user) < 2500 else "primary"
            i += 1
            if len(results[slot]) >= 20:
                continue
            t0 = time.perf_counter()
            response = client.post(
                "/recommend", json={"user_id": user, "algorithm": "ranked", "source": "load_test"}
            )
            response.raise_for_status()
            data = response.json()
            results[slot].append(
                {
                    "latency_ms": (time.perf_counter() - t0) * 1000,
                    "injected_failure": data["fallback_reason"] == "retrieval_failure",
                }
            )
        observed = {
            slot: {
                "requests": len(rows),
                "p95_ms": float(np.quantile([x["latency_ms"] for x in rows], 0.95)),
                "retrieval_failure_rate": np.mean([x["injected_failure"] for x in rows]).item(),
            }
            for slot, rows in results.items()
        }
        triggered = (
            observed["canary"]["retrieval_failure_rate"]
            > observed["primary"]["retrieval_failure_rate"] + 0.2
        )
        if triggered:
            rollback(state)
        probe = client.post(
            "/recommend", json={"user_id": "rollout-user-0", "source": "load_test"}
        ).json()
    report = {
        "traffic": "Synthetic local TestClient traffic; no online quality or business claim",
        "injection": "Canary-only 25 ms delay and retrieval exception",
        "guard": "Canary retrieval-failure rate exceeds primary by 0.2",
        "observed": observed,
        "rollback_triggered": bool(triggered),
        "post_rollback_slot": probe["experiment_slot"],
        "post_rollback_version": probe["model_version"],
    }
    Path(output).write_text(json.dumps(report, indent=2))
    return report


def verify_local(bundle_path, output, rate=50, duration=10, check_ui=False):
    """Start a real HTTP server and client in the same host/network environment."""
    import uvicorn

    with tempfile.TemporaryDirectory(prefix="atlas-http-") as temporary:
        root = Path(temporary)
        activate(root / "registry.json", bundle_path)
        app = create_app(root / "registry.json", root / "feedback.sqlite", api_key="")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 20
            while not server.started:
                if time.monotonic() >= deadline or not thread.is_alive():
                    raise RuntimeError("Local API did not start")
                time.sleep(0.05)
            url = f"http://127.0.0.1:{port}"
            report = asyncio.run(load_test(url, bundle_path, output, rate, duration))
            if check_ui:
                from streamlit.testing.v1 import AppTest

                os.environ["ATLAS_API_URL"] = url
                os.environ["ATLAS_DEMO_BUNDLE"] = str(bundle_path)
                at = AppTest.from_file(
                    str(Path(__file__).with_name("ui.py")), default_timeout=20
                ).run()
                if at.exception:
                    raise RuntimeError(str(at.exception))
                next(b for b in at.button if b.label == "Recommend").click().run()
                if at.exception or at.error or "result" not in at.session_state:
                    raise RuntimeError("Existing-user UI flow failed")
                at.radio[0].set_value("New user").run()
                category = sorted({x["category"] for x in Bundle(bundle_path).items})[0]
                at.multiselect[0].set_value([category]).run()
                next(b for b in at.button if b.label == "Recommend").click().run()
                if (
                    at.exception
                    or at.error
                    or not at.session_state["result"]["onboarding_preferences_used"]
                ):
                    raise RuntimeError("Onboarding UI flow failed")
                next(b for b in at.button if b.label == "Useful recommendation").click().run()
                if at.exception or at.error:
                    raise RuntimeError("Feedback UI flow failed")
                report["ui_checks"] = [
                    "existing-user recommendations",
                    "new-user preferences",
                    "feedback",
                ]
                Path(output).write_text(json.dumps(report, indent=2))
            return report
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            sock.close()
