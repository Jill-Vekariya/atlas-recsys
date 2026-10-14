import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.cohort_evidence import summarize  # noqa: E402


def report():
    def m(ndcg, returning):
        return {
            "ndcg_at_10": ndcg,
            "returning_ndcg_at_10": returning,
            "new_user_ndcg_at_10": 0.3,
            "controlled_cold_recall_at_100": 0.01,
            "cold_evaluation_users": 5,
            "returning_users": 3,
            "fallback_rate": 0.7,
        }

    return {
        "source": "fixture",
        "split": "validation",
        "population": {"sampled_users": 10},
        "results": {"popularity": m(0.2, 0.1), "tower": m(0.18, 0.14)},
    }


def test_separates_returning_and_new_without_inventing_uncertainty():
    result = summarize(report())
    assert result["returning_users"] == 3
    assert result["new_users"] == 7
    assert result["models"]["tower"]["returning_minus_popularity_ndcg_at_10"] == pytest.approx(0.04)
    assert "no new" in result["limitations"]


def test_rejects_non_evaluation_and_mismatched_cohorts():
    data = report()
    data["split"] = "training"
    with pytest.raises(ValueError):
        summarize(data)
    data = report()
    data["results"]["tower"]["returning_users"] = 4
    with pytest.raises(ValueError):
        summarize(data)
