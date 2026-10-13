import numpy as np
import pandas as pd
import pytest
import torch

from atlas.data import read_prepared, validate
from atlas.evaluation import metrics, paired_interval
from atlas.features import context, histories
from atlas.models import TwoTower, multi_positive_loss, training_examples


def test_strict_cutoff_excludes_future_and_equal_time():
    events = pd.DataFrame(
        [("u", "a", 9, 5), ("u", "b", 10, 5), ("u", "c", 11, 5)],
        columns=["user_id", "item_id", "timestamp", "rating"],
    )
    state = histories(events, {"a": 0, "b": 1, "c": 2}, 10, 4)
    assert state["u"]["positive"] == [0]


def test_dislikes_are_excluded_but_not_positive_history():
    events = pd.DataFrame([("u", "a", 9, 2)], columns=["user_id", "item_id", "timestamp", "rating"])
    state = histories(events, {"a": 0}, 10, 4)
    assert state["u"] == {"seen": [0], "positive": []}


def test_cold_items_absent_from_both_training_windows(trained):
    cfg, _ = trained
    items, events, _ = read_prepared(cfg)
    cold = set(items[items.controlled_cold].item_id)
    training = events[events.split.isin(["retriever", "ranker"])]
    assert cold
    assert not set(training.item_id) & cold


def test_temporal_windows_do_not_overlap(trained):
    cfg, _ = trained
    _, events, _ = read_prepared(cfg)
    periods = [
        events[events.split == s].timestamp for s in ["retriever", "ranker", "validation", "test"]
    ]
    assert all(a.max() < b.min() for a, b in zip(periods, periods[1:]))


def test_examples_never_use_target_or_future_context():
    events = pd.DataFrame(
        [
            ("u", "a", 1, 5, "retriever"),
            ("u", "b", 2, 5, "retriever"),
            ("u", "c", 2, 5, "retriever"),
        ],
        columns=["user_id", "item_id", "timestamp", "rating", "split"],
    )
    examples = training_examples(
        events,
        {"a": 0, "b": 1, "c": 2},
        np.eye(3, dtype=np.float32),
        {"positive_rating": 4, "history_size": 20},
    )
    assert len(examples) == 2
    for x, target, seen in examples:
        assert seen == {0}
        np.testing.assert_array_equal(x, [1, 0, 0])
        assert target not in seen


def test_duplicate_batch_positives_are_not_negatives():
    logits = torch.zeros(2, 2, requires_grad=True)
    loss = multi_positive_loss(logits, torch.tensor([3, 3]), torch.ones(2, 2, dtype=torch.bool))
    assert loss.item() == 0
    loss.backward()
    assert torch.isfinite(logits.grad).all()


def test_torch_export_matches_numpy_inference(trained):
    cfg, bundle = trained
    model = TwoTower(len(bundle.items), bundle.content.shape[1], cfg["embedding_dim"])
    model.load_state_dict(torch.load(bundle.path / "tower.pt", weights_only=True))
    h = [0, 1, 2]
    x = context(h, bundle.content, cfg["history_size"])
    expected = torch.nn.functional.normalize(model.user(torch.from_numpy(x[None])), dim=1)
    np.testing.assert_allclose(bundle.query_vector(h), expected.detach().numpy(), atol=1e-6)


def test_metrics_known_answer():
    result = metrics([5, 2, 3], {2, 9})
    assert result["recall_at_100"] == 0.5
    assert result["precision_at_10"] == 0.1
    assert result["ndcg_at_10"] == pytest.approx((1 / np.log2(3)) / (1 + 1 / np.log2(3)))


def test_paired_ci_identical_models():
    interval = paired_interval([0.1, 0.2], [0.1, 0.2], 100, 42)
    assert interval["ci95"] == [0, 0]


def test_invalid_ratings_rejected():
    items = pd.DataFrame(
        [("a", "a", "cat", "text")], columns=["item_id", "title", "category", "text"]
    )
    events = pd.DataFrame([("u", "a", 1, 8)], columns=["user_id", "item_id", "timestamp", "rating"])
    with pytest.raises(ValueError, match="ratings"):
        validate(items, events)
