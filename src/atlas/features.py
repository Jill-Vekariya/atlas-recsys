"""One feature implementation shared by evaluation and serving."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import pandas as pd

FEATURE_NAMES = [
    "retrieval_similarity",
    "content_similarity",
    "category_affinity",
    "log_popularity",
    "log_history_length",
    "recent_content_similarity",
]


def fit_content(items: pd.DataFrame, dim: int, seed: int):
    from sklearn.decomposition import TruncatedSVD
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import normalize

    vectorizer = TfidfVectorizer(max_features=10000, min_df=1, stop_words="english")
    texts = (items.title + " " + items.text + " " + items.category).replace("", "unknown")
    sparse = vectorizer.fit_transform(texts)
    n_components = max(1, min(dim, sparse.shape[1] - 1, sparse.shape[0] - 1))
    svd = TruncatedSVD(n_components=n_components, random_state=seed)
    content = normalize(svd.fit_transform(sparse)).astype(np.float32)
    return content, vectorizer, svd


def histories(events: pd.DataFrame, item_map: dict, cutoff: int, positive_rating: float):
    """Strictly earlier events, including dislikes for exclusion but not positive history."""
    result = {}
    for row in events[events.timestamp < cutoff].itertuples():
        state = result.setdefault(str(row.user_id), {"positive": [], "seen": []})
        idx = item_map[row.item_id]
        state["seen"].append(idx)
        if row.rating >= positive_rating:
            state["positive"].append(idx)
    return result


def context(history: list[int], content: np.ndarray, limit: int, recency: bool = True):
    chosen = history[-limit:]
    if not chosen:
        return np.zeros(content.shape[1], dtype=np.float32)
    weights = np.exp(np.linspace(-1, 0, len(chosen))) if recency else np.ones(len(chosen))
    return np.average(content[chosen], axis=0, weights=weights).astype(np.float32)


def l2_normalize(x: np.ndarray):
    return x / np.maximum(np.linalg.norm(x, axis=-1, keepdims=True), 1e-9)


def rank_features(indices, retrieval_scores, history, content, popularity, categories, limit):
    idx = np.asarray(indices, dtype=int)
    ctx = l2_normalize(context(history, content, limit).reshape(1, -1))[0]
    recent = content[history[-1]] if history else np.zeros_like(ctx)
    counts = {}
    for i in history[-limit:]:
        counts[categories[i]] = counts.get(categories[i], 0) + 1
    denominator = max(1, len(history[-limit:]))
    return np.column_stack(
        [
            retrieval_scores,
            content[idx] @ ctx,
            [counts.get(categories[i], 0) / denominator for i in idx],
            np.log1p(popularity[idx]),
            np.full(len(idx), np.log1p(len(history))),
            content[idx] @ recent,
        ]
    ).astype(np.float32)


def fold_in_als(history, factors, alpha=20.0, regularization=0.1, gram=None):
    if not history:
        return np.zeros(factors.shape[1], dtype=np.float32)
    ids, counts = np.unique(history, return_counts=True)
    y = factors[ids]
    confidence = alpha * counts.astype(np.float32)
    system = (factors.T @ factors if gram is None else gram.copy()) + (y.T * (confidence - 1)) @ y
    system += np.eye(factors.shape[1], dtype=np.float32) * regularization
    return np.linalg.solve(system, y.T @ confidence).astype(np.float32)
