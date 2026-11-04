"""Audit validation-only model selection against recorded held-out evaluation.

Never use the test report to change the selected model.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def audit(validation: dict, test: dict) -> dict:
    if validation.get("split") != "validation" or test.get("split") != "test":
        raise ValueError("Expected validation and test reports, respectively")
    for key in ("source", "synthetic"):
        if validation.get(key) != test.get(key):
            raise ValueError(f"Reports disagree on {key}")
    val = validation["results"]
    heldout = test["results"]
    if set(val) != set(heldout):
        raise ValueError("Validation/test model sets differ; missing tests cannot change selection")
    names = sorted(val)
    if not names:
        raise ValueError("No models shared between reports")
    available = {name: val[name].get("ndcg_at_10") for name in names}
    available = {name: score for name, score in available.items() if score is not None}
    if any(
        type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1
        for score in available.values()
    ):
        raise ValueError("Finite validation NDCG scores in [0,1] required")
    if not available:
        raise ValueError("No valid validation NDCG@10 scores")
    # Match the training pipeline's tie-breaking: use validation report insertion order.
    selected = max(
        (name for name in val if name in available),
        key=lambda name: available[name],
    )
    recorded = validation.get("selected_algorithm")
    if recorded is not None and recorded != selected:
        raise ValueError("Recorded selected algorithm conflicts with validation winner")
    rows = []
    for name in names:
        v = val[name]
        t = heldout[name]
        rows.append(
            {
                "algorithm": name,
                "validation_ndcg_at_10": v.get("ndcg_at_10"),
                "test_ndcg_at_10": t.get("ndcg_at_10"),
                "test_returning_ndcg_at_10": t.get("returning_ndcg_at_10"),
                "test_controlled_cold_recall_at_100": t.get("controlled_cold_recall_at_100"),
                "selected_by_validation": name == selected,
            }
        )
    baseline = heldout.get("popularity", {}).get("ndcg_at_10")
    chosen = heldout[selected].get("ndcg_at_10")
    return {
        "source": validation["source"],
        "synthetic": validation["synthetic"],
        "selection_metric": "validation macro NDCG@10",
        "validation_selected_algorithm": selected,
        "validation_users": validation.get("population", {}).get("sampled_users"),
        "test_users": test.get("population", {}).get("sampled_users"),
        "test_selected_ndcg_at_10": chosen,
        "test_popularity_ndcg_at_10": baseline,
        "test_selected_minus_popularity_ndcg_at_10": (
            chosen - baseline if chosen is not None and baseline is not None else None
        ),
        "algorithms": rows,
        "interpretation": (
            "Selection was determined exclusively from validation results. "
            "Test metrics are a held-out diagnostic, not an input to selection. "
            "The score difference is descriptive, not a significance claim."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", type=Path, required=True)
    args = parser.parse_args()
    path = args.report_dir
    validation = json.loads((path / "validation.json").read_text(encoding="utf-8"))
    test = json.loads((path / "test.json").read_text(encoding="utf-8"))
    print(json.dumps(audit(validation, test), indent=2))


if __name__ == "__main__":
    main()
