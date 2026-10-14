"""Regression checks for validation-only portfolio model-selection evidence."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.model_selection_audit import audit  # noqa: E402


def report(split, a, b):
    return {
        "split": split,
        "source": "fixture",
        "synthetic": True,
        "population": {"sampled_users": 3},
        "results": {
            "popularity": {"ndcg_at_10": a},
            "tower": {"ndcg_at_10": b},
        },
    }


def test_validation_selection_unchanged_by_test_performance():
    val = report("validation", 0.2, 0.3)
    test = report("test", 0.9, 0.1)
    result = audit(val, test)
    assert result["validation_selected_algorithm"] == "tower"
    assert result["test_selected_minus_popularity_ndcg_at_10"] == pytest.approx(-0.8)


def test_rejects_incorrect_splits_and_mixed_sources():
    val = report("validation", 0.1, 0.2)
    heldout = report("test", 0.1, 0.2)
    with pytest.raises(ValueError, match="validation and test"):
        audit(heldout, val)
    heldout["source"] = "other"
    with pytest.raises(ValueError, match="source"):
        audit(val, heldout)


def test_detects_inconsistent_recorded_selection():
    val = report("validation", 0.1, 0.2)
    val["selected_algorithm"] = "popularity"
    with pytest.raises(ValueError, match="conflicts"):
        audit(val, report("test", 0.2, 0.1))


def test_validation_ties_follow_pipeline_order():
    val = report("validation", 0.2, 0.2)
    assert audit(val, report("test", 0.1, 0.9))["validation_selected_algorithm"] == ("popularity")
