"""Read-only diagnosis of recorded cohort results; no new training or test-based selection."""

import argparse
import json
from pathlib import Path


def summarize(report):
    if report.get("split") not in ("validation", "test"):
        raise ValueError("A validation or test report is required")
    rows = report["results"]
    if "popularity" not in rows:
        raise ValueError("Popularity comparison is required")
    n = report["population"]["sampled_users"]
    returning = rows["popularity"]["returning_users"]
    if not 0 <= returning <= n:
        raise ValueError("Invalid returning-user cohort")
    cohorts = {}
    for name, metric in rows.items():
        if metric["returning_users"] != returning:
            raise ValueError("Inconsistent user cohorts across algorithms")
        cohorts[name] = {
            "overall_ndcg_at_10": metric["ndcg_at_10"],
            "returning_ndcg_at_10": metric["returning_ndcg_at_10"],
            "new_user_ndcg_at_10": metric["new_user_ndcg_at_10"],
            "controlled_cold_recall_at_100": metric["controlled_cold_recall_at_100"],
            "cold_target_users": metric["cold_evaluation_users"],
            "fallback_rate": metric["fallback_rate"],
            "returning_minus_popularity_ndcg_at_10": (
                metric["returning_ndcg_at_10"] - rows["popularity"]["returning_ndcg_at_10"]
                if metric["returning_ndcg_at_10"] is not None
                and rows["popularity"]["returning_ndcg_at_10"] is not None
                else None
            ),
        }
    return {
        "source": report["source"],
        "split": report["split"],
        "total_users": n,
        "returning_users": returning,
        "new_users": n - returning,
        "models": cohorts,
        "recorded_paired_comparisons": report.get("paired_comparisons", {}),
        "limitations": (
            "Aggregated historical results only; no new experiment, new confidence interval, "
            "statistical significance test, retraining, or model selection. "
            "The original user-level results are needed for new paired subgroup uncertainty."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    print(json.dumps(summarize(report), indent=2))


if __name__ == "__main__":
    main()
