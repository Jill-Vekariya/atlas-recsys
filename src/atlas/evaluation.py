"""Full-catalog relevance, subgroup diagnostics, and paired uncertainty."""

import time
from pathlib import Path

import numpy as np

from atlas.features import histories
from atlas.reports import write_new_report

ALGORITHMS = ["popularity", "category_popularity", "als", "content", "tower", "ranked"]


def metrics(recommendations, positives):
    positives = set(positives)
    if not positives:
        raise ValueError("Metrics require at least one eligible positive")
    top10 = list(recommendations[:10])
    recall = len(set(recommendations[:100]) & positives) / len(positives)
    gains = [int(i in positives) for i in top10]
    dcg = sum(g / np.log2(r + 2) for r, g in enumerate(gains))
    ideal = sum(1 / np.log2(r + 2) for r in range(min(10, len(positives))))
    return {
        "recall_at_100": float(recall),
        "ndcg_at_10": float(dcg / ideal),
        "precision_at_10": float(sum(gains) / 10),
    }


def queries(bundle, events, split, cfg):
    key = "ranker_end" if split == "validation" else "validation_end"
    cutoff = bundle.manifest["dataset"]["boundaries"][key]
    states = histories(events, bundle.item_map, cutoff, cfg["positive_rating"])
    window = events[(events.split == split) & (events.rating >= cfg["positive_rating"])]
    result = []
    for user, rows in window.groupby("user_id", sort=True):
        state = states.get(str(user), {"positive": [], "seen": []})
        seen = set(state["seen"])
        truth = sorted({bundle.item_map[i] for i in rows.item_id} - seen)
        if truth:
            result.append((str(user), state["positive"], seen, truth))
    # Deterministic uniform sample of eligible users, never chosen by model performance.
    rng = np.random.default_rng(cfg["seed"])
    count = min(cfg["max_eval_users"], len(result))
    selected = sorted(rng.choice(len(result), count, replace=False)) if count else []
    return [result[i] for i in selected], {
        "eligible_users": len(result),
        "sampled_users": count,
        "prediction_cutoff": cutoff,
    }


def paired_interval(a, b, samples, seed):
    differences = np.asarray(a) - np.asarray(b)
    if not len(differences):
        return None
    rng = np.random.default_rng(seed)
    means = [
        float(rng.choice(differences, len(differences), replace=True).mean())
        for _ in range(samples)
    ]
    return {
        "mean_delta": float(differences.mean()),
        "ci95": [float(x) for x in np.quantile(means, [0.025, 0.975])],
        "unit": "absolute NDCG@10",
        "resampling_unit": "user",
    }


def evaluate(bundle, events, cfg, split="validation", write=True):
    rows, population = queries(bundle, events, split, cfg)
    results, individual = {}, {}
    for algorithm in ALGORITHMS:
        user_metrics, recommended, latencies, subgroup, fallback = [], set(), [], [], 0
        for user, history, seen, truth in rows:
            t0 = time.perf_counter()
            ids, _, reason, _ = bundle.candidates(
                history, seen, max(100, cfg["candidate_count"]), algorithm
            )
            latencies.append((time.perf_counter() - t0) * 1000)
            m = metrics(ids.tolist(), truth)
            user_metrics.append(m)
            recommended.update(int(i) for i in ids[:10])
            fallback += reason is not None
            cold_truth = [i for i in truth if bundle.items[i]["controlled_cold"]]
            subgroup.append(
                {
                    "user": user,
                    "history_group": "returning" if history else "new",
                    "history_length": len(history),
                    "metrics": m,
                    "cold_recall_at_100": len(set(ids[:100]) & set(cold_truth)) / len(cold_truth)
                    if cold_truth
                    else None,
                    "head_recall_at_100": _cohort_recall(ids, truth, bundle.popularity, "head"),
                    "low_history_recall_at_100": _cohort_recall(
                        ids, truth, bundle.popularity, "low"
                    ),
                    "zero_history_recall_at_100": _cohort_recall(
                        ids, truth, bundle.popularity, "zero"
                    ),
                }
            )
        individual[algorithm] = [x["ndcg_at_10"] for x in user_metrics]

        def average(values):
            values = [v for v in values if v is not None]
            return float(np.mean(values)) if values else None

        result = {
            key: average([m[key] for m in user_metrics])
            for key in ("recall_at_100", "ndcg_at_10", "precision_at_10")
        }
        result.update(
            {
                "catalog_coverage_at_10": len(recommended) / len(bundle.items),
                "mean_recommended_train_popularity": average(
                    [float(bundle.popularity[i]) for i in recommended]
                ),
                "fallback_rate": fallback / max(1, len(rows)),
                "local_sequential_p95_ms": float(np.quantile(latencies, 0.95))
                if latencies
                else None,
                "returning_users": sum(bool(h) for _, h, _, _ in rows),
                "returning_ndcg_at_10": average(
                    [
                        x["metrics"]["ndcg_at_10"]
                        for x in subgroup
                        if x["history_group"] == "returning"
                    ]
                ),
                "new_user_ndcg_at_10": average(
                    [x["metrics"]["ndcg_at_10"] for x in subgroup if x["history_group"] == "new"]
                ),
                "controlled_cold_recall_at_100": average(
                    [x["cold_recall_at_100"] for x in subgroup]
                ),
                "returning_controlled_cold_recall_at_100": average(
                    [x["cold_recall_at_100"] for x in subgroup if x["history_group"] == "returning"]
                ),
                "returning_cold_evaluation_users": sum(
                    x["cold_recall_at_100"] is not None and x["history_group"] == "returning"
                    for x in subgroup
                ),
                "cold_evaluation_users": sum(x["cold_recall_at_100"] is not None for x in subgroup),
                "head_recall_at_100": average([x["head_recall_at_100"] for x in subgroup]),
                "low_history_recall_at_100": average(
                    [x["low_history_recall_at_100"] for x in subgroup]
                ),
                "zero_history_recall_at_100": average(
                    [x["zero_history_recall_at_100"] for x in subgroup]
                ),
            }
        )
        results[algorithm] = result
    report = {
        "source": bundle.manifest["dataset"]["source"],
        "synthetic": bundle.manifest["dataset"]["synthetic"],
        "split": split,
        "protocol": "Full fixed catalog snapshot; exclude all pre-cutoff rated items; macro average users",
        "population": population,
        "results": results,
        "paired_comparisons": {
            "ranked_minus_als": paired_interval(
                individual["ranked"], individual["als"], cfg["bootstrap_samples"], cfg["seed"]
            ),
            "tower_minus_content": paired_interval(
                individual["tower"], individual["content"], cfg["bootstrap_samples"], cfg["seed"]
            ),
        },
        "limitations": [
            "Review/rating preference proxy; no business uplift",
            "Metadata snapshot is not historically reconstructed",
            "Single seed; confidence intervals do not include training variance",
            "Latency here is in-process and sequential, not an HTTP load test",
        ],
    }
    if write:
        out = Path(cfg["report_dir"])
        out.mkdir(parents=True, exist_ok=True)
        write_new_report(out / f"{split}.json", report)
    return report


def _cohort_recall(ids, truth, popularity, kind):
    positives = [
        i
        for i in truth
        if (
            popularity[i] >= 5
            if kind == "head"
            else 0 < popularity[i] < 5
            if kind == "low"
            else popularity[i] == 0
        )
    ]
    return len(set(ids[:100]) & set(positives)) / len(positives) if positives else None


def tradeoffs(bundle, events, cfg):
    rows, _ = queries(bundle, events, "validation", cfg)
    rows = [x for x in rows if x[1]][:100]
    results = []
    original_ef = bundle.approx.hnsw.efSearch
    try:
        for ef in [8, 32, 128]:
            bundle.approx.hnsw.efSearch = ef
            for k in [20, 100, 200]:
                recalls, ndcgs, times = [], [], []
                for _, history, seen, truth in rows:
                    exact, _, _, _ = bundle.candidates(history, seen, k, "tower", approximate=False)
                    t0 = time.perf_counter()
                    ann, _, _, _ = bundle.candidates(history, seen, k, "tower", approximate=True)
                    times.append((time.perf_counter() - t0) * 1000)
                    recalls.append(len(set(exact) & set(ann)) / max(1, len(exact)))
                    ndcgs.append(metrics(ann.tolist(), truth)["ndcg_at_10"])
                results.append(
                    {
                        "ef_search": ef,
                        "candidate_count": k,
                        "queries": len(rows),
                        "ann_recall_vs_exact": float(np.mean(recalls)) if recalls else None,
                        "ndcg_at_10": float(np.mean(ndcgs)) if ndcgs else None,
                        "sequential_p95_ms": float(np.quantile(times, 0.95)) if times else None,
                    }
                )
    finally:
        bundle.approx.hnsw.efSearch = original_ef
    recency = {}
    for weighted in [False, True]:
        values = []
        for _, h, s, truth in rows:
            ids, _, _, _ = bundle.candidates(h, s, 100, "tower", recency=weighted)
            values.append(metrics(ids.tolist(), truth)["ndcg_at_10"])
        recency["weighted" if weighted else "uniform"] = float(np.mean(values)) if values else None
    report = {
        "split": "validation",
        "synthetic": bundle.manifest["dataset"]["synthetic"],
        "ann_tradeoffs": results,
        "history_weighting_ablation": recency,
    }
    out = Path(cfg["report_dir"])
    out.mkdir(parents=True, exist_ok=True)
    write_new_report(out / "tradeoffs.json", report)
    return report
