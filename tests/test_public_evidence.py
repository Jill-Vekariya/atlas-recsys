"""Public experiment evidence cannot accidentally select on held-out test data."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.export_browser_bundle import selection_evidence  # noqa: E402


def make_report(split, popularity, tower):
    return {
        "source": "movielens",
        "synthetic": False,
        "split": split,
        "population": {
            "sampled_users": 30,
            "prediction_cutoff": 10 if split == "validation" else 20,
        },
        "results": {
            "popularity": {
                "ndcg_at_10": popularity,
                "local_sequential_p95_ms": 1.1,
                "returning_users": 8,
                "cold_evaluation_users": 12,
            },
            "tower": {
                "ndcg_at_10": tower,
                "local_sequential_p95_ms": 2.2,
                "returning_users": 8,
                "cold_evaluation_users": 12,
            },
        },
    }


def test_selection_uses_validation_not_test():
    validation = make_report("validation", 0.3, 0.4)
    test = make_report("test", 0.9, 0.1)
    result = selection_evidence(validation, test, "movielens")
    assert result["validation_selected"] == "tower"
    assert result["selected_minus_popularity_test_ndcg"] == pytest.approx(-0.8)
    assert result["validation_metrics"]["tower"]["sequential_p95_ms"] == 2.2
    assert result["test_returning_users"] == 8


@pytest.mark.parametrize("field", ["source", "synthetic", "split"])
def test_mixed_or_mislabeled_evidence_is_rejected(field):
    validation = make_report("validation", 0.3, 0.4)
    test = make_report("test", 0.3, 0.4)
    test[field] = {"source": "amazon", "synthetic": True, "split": "validation"}[field]
    with pytest.raises(ValueError):
        selection_evidence(validation, test, "movielens")


def test_chronology_and_recorded_selection_are_checked():
    validation = make_report("validation", 0.3, 0.4)
    test = make_report("test", 0.3, 0.4)
    test["population"]["prediction_cutoff"] = 5
    with pytest.raises(ValueError, match="precede"):
        selection_evidence(validation, test, "movielens")
    test["population"]["prediction_cutoff"] = 20
    validation["selected_algorithm"] = "popularity"
    with pytest.raises(ValueError, match="selection"):
        selection_evidence(validation, test, "movielens")
