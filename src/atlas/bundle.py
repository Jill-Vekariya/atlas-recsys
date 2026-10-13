"""Immutable, verified serving bundles. Only load artifacts built by a trusted operator."""

import json
import time
from pathlib import Path

import faiss
import lightgbm as lgb
import numpy as np

from atlas.features import FEATURE_NAMES, context, fold_in_als, l2_normalize, rank_features
from atlas.utils import sha256


class Bundle:
    def __init__(self, directory: str | Path):
        self.path = Path(directory).resolve()
        self.manifest = json.loads((self.path / "bundle.json").read_text())
        if self.manifest["schema_version"] != 1:
            raise ValueError("Unsupported bundle schema")
        if self.manifest["feature_names"] != FEATURE_NAMES:
            raise ValueError("Feature schema mismatch")
        for name, checksum in self.manifest["assets"].items():
            p = (self.path / name).resolve()
            if not p.is_relative_to(self.path) or sha256(p) != checksum:
                raise ValueError(f"Bundle checksum mismatch: {name}")
        self.items = json.loads((self.path / "items.json").read_text())
        self.histories = json.loads((self.path / "histories.json").read_text())
        self.item_map = {x["item_id"]: i for i, x in enumerate(self.items)}
        self.categories = np.array([x["category"] for x in self.items])
        arrays = np.load(self.path / "arrays.npz", allow_pickle=False)
        self.content = arrays["content"]
        self.vectors = arrays["vectors"]
        self.user_weights = arrays["user_weights"]
        self.als_factors = arrays["als_factors"]
        self.als_gram = self.als_factors.T @ self.als_factors
        self.popularity = arrays["popularity"]
        self.exact = faiss.read_index(str(self.path / "exact.faiss"))
        self.approx = faiss.read_index(str(self.path / "hnsw.faiss"))
        self.ranker = (
            lgb.Booster(model_file=str(self.path / "ranker.txt"))
            if (self.path / "ranker.txt").exists()
            else None
        )
        n = len(self.items)
        if self.exact.ntotal != n or self.approx.ntotal != n:
            raise ValueError("Index/item mapping mismatch")
        for a in (self.content, self.vectors, self.als_factors, self.popularity):
            if len(a) != n or not np.isfinite(a).all():
                raise ValueError("Invalid serving arrays")
        if self.user_weights.shape != (self.vectors.shape[1], self.content.shape[1]):
            raise ValueError("Projection/content shape mismatch")
        if self.exact.d != self.vectors.shape[1] or self.approx.d != self.exact.d:
            raise ValueError("Index/vector dimensional mismatch")
        if self.ranker is not None and self.ranker.num_feature() != len(FEATURE_NAMES):
            raise ValueError("Ranker feature mismatch")
        self.config = self.manifest["config"]
        self.version = self.manifest["version"]
        faiss.omp_set_num_threads(self.config["threads"])

    def query_vector(self, history, recency=True):
        ctx = context(history, self.content, self.config["history_size"], recency)
        return l2_normalize((ctx @ self.user_weights.T).reshape(1, -1)).astype(np.float32)

    def candidates(
        self, history, seen, k, algorithm="ranked", approximate=True, category=None, recency=True
    ):
        faiss.omp_set_num_threads(self.config["threads"])
        n = len(self.items)
        seen = set(seen)
        eligible = np.array(
            [
                i
                for i in range(n)
                if i not in seen and (category is None or self.categories[i] == category)
            ],
            dtype=int,
        )
        k = min(k, len(eligible))
        reason = None
        t0 = time.perf_counter()
        if k == 0:
            return (
                np.array([], dtype=int),
                np.array([], dtype=np.float32),
                None,
                {
                    "retrieval_ms": 0.0,
                    "ranking_ms": 0.0,
                },
            )
        if not history and algorithm != "popularity":
            algorithm, reason = "popularity", "no_positive_history"
        if algorithm in ("popularity", "category_popularity"):
            scores = self.popularity.astype(float).copy()
            if algorithm == "category_popularity":
                counts = {}
                for i in history[-self.config["history_size"] :]:
                    counts[self.categories[i]] = counts.get(self.categories[i], 0) + 1
                scores += np.array([counts.get(cat, 0) for cat in self.categories]) * (
                    1 + float(self.popularity.max())
                )
            indices = eligible[np.argsort(-scores[eligible], kind="stable")[:k]]
            selected_scores = scores[indices]
        elif algorithm == "als":
            q = fold_in_als(history, self.als_factors, gram=self.als_gram)
            if float(np.linalg.norm(q)) < 1e-9:
                # Content remains informative when every onboarding seed has zero ALS factors.
                q = l2_normalize(
                    context(history, self.content, self.config["history_size"], recency).reshape(1, -1)
                )[0]
                scores = self.content @ q
                reason = "als_no_signal"
            else:
                scores = self.als_factors @ q
            indices = eligible[np.argsort(-scores[eligible], kind="stable")[:k]]
            selected_scores = scores[indices]
        elif algorithm == "content":
            q = l2_normalize(
                context(history, self.content, self.config["history_size"], recency).reshape(1, -1)
            )[0]
            scores = self.content @ q
            indices = eligible[np.argsort(-scores[eligible], kind="stable")[:k]]
            selected_scores = scores[indices]
        elif algorithm in ("tower", "ranked"):
            q = self.query_vector(history, recency)
            # Metadata filtering uses exact scoring to avoid post-filter retrieval starvation.
            if category is not None:
                scores = self.vectors @ q[0]
                indices = eligible[np.argsort(-scores[eligible], kind="stable")[:k]]
                selected_scores = scores[indices]
            else:
                index = self.approx if approximate else self.exact
                scores, found = index.search(q, min(n, k + len(seen)))
                chosen = [
                    (int(i), float(s))
                    for i, s in zip(found[0], scores[0], strict=True)
                    if i >= 0 and int(i) not in seen
                ][:k]
                indices = np.array([x[0] for x in chosen], dtype=int)
                selected_scores = np.array([x[1] for x in chosen], dtype=np.float32)
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}")
        retrieval_ms = (time.perf_counter() - t0) * 1000
        t1 = time.perf_counter()
        if algorithm == "ranked" and len(indices):
            if self.ranker is None:
                reason = "ranker_unavailable"
            else:
                features = rank_features(
                    indices,
                    selected_scores,
                    history,
                    self.content,
                    self.popularity,
                    self.categories,
                    self.config["history_size"],
                )
                selected_scores = self.ranker.predict(features, num_threads=self.config["threads"])
                order = np.argsort(-selected_scores, kind="stable")
                indices, selected_scores = indices[order], selected_scores[order]
        return (
            indices,
            selected_scores,
            reason,
            {
                "retrieval_ms": retrieval_ms,
                "ranking_ms": (time.perf_counter() - t1) * 1000,
            },
        )

    def explain(self, index: int, history: list[int]):
        ctx = context(history, self.content, self.config["history_size"])
        sim = float(self.content[index] @ l2_normalize(ctx.reshape(1, -1))[0])
        pop = int(self.popularity[index])
        return {
            "content_similarity": round(sim, 4),
            "retriever_training_positive_count": pop,
            "controlled_cold_item": bool(self.items[index]["controlled_cold"]),
            "history_length": len(history),
            "interpretation": "Feature diagnostics; not a causal explanation or probability",
        }
