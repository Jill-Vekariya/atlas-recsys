import pytest

from atlas.study import summarize, verify_dataset, file_hash
import json
from scripts.model_selection_audit import audit


def test_negative_seed_and_missing_cohort_are_preserved():
    def row(seed, delta):
        return {
            "seed": seed,
            "status": "evaluated",
            "selected_algorithm": "tower",
            "test": {
                "results": {"popularity": {"ndcg_at_10": 0.5}, "tower": {"ndcg_at_10": 0.5 + delta}}
            },
        }

    result = summarize(
        [row(17, -0.2), row(29, 0.1), {"seed": 41, "status": "failed"}], [17, 29, 41]
    )
    scores = result["selected_minus_popularity"]["ndcg_at_10"]
    assert scores["negative_seeds"] == 1 and scores["mean_delta"] == pytest.approx(-0.05)
    assert result["failed_seeds"] == [41] and result["not_evaluated_seeds"] == [41]
    assert result["selected_minus_popularity"]["new_user_ndcg_at_10"]["mean_delta"] is None


def test_test_missing_winner_cannot_reselect_validation_runner_up():
    val = {
        "split": "validation",
        "source": "fixture",
        "synthetic": True,
        "results": {"popularity": {"ndcg_at_10": 0.1}, "tower": {"ndcg_at_10": 0.5}},
    }
    test = {**val, "split": "test", "results": {"popularity": {"ndcg_at_10": 0.9}}}
    with pytest.raises(ValueError, match="model sets"):
        audit(val, test)


def test_changed_dataset_cannot_pass_manifest_only_check(tmp_path):
    data = tmp_path / "items.parquet"
    data.write_bytes(b"frozen-fixture")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"checksums": {data.name: file_hash(data)}}))
    expected = file_hash(manifest)
    verify_dataset(tmp_path, expected)
    data.write_bytes(b"changed")
    with pytest.raises(ValueError, match="bytes changed"):
        verify_dataset(tmp_path, expected)


@pytest.mark.parametrize("score", [float("nan"), float("inf"), True, -1, 2])
def test_invalid_validation_metric_is_rejected(score):
    val = {
        "split": "validation",
        "source": "fixture",
        "synthetic": True,
        "results": {"popularity": {"ndcg_at_10": score}},
    }
    with pytest.raises(ValueError, match="Finite"):
        audit(val, {**val, "split": "test"})
