from concurrent.futures import ThreadPoolExecutor

from atlas.storage import Store


def test_concurrent_feedback_retry_is_idempotent(tmp_path):
    store = Store(tmp_path / "feedback.sqlite")
    store.exposure("r", "u", "demo", "v", "primary", ["i"])
    event = {"event_id": "same", "request_id": "r", "item_id": "i", "signal": "like"}
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: store.feedback(event), range(16)))
    assert sum(results) == 1
