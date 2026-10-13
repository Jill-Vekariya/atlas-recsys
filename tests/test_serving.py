import json
import shutil

import pytest
from fastapi.testclient import TestClient

from atlas.api import create_app
from atlas.bundle import Bundle
from atlas.registry import Registry, activate, bucket, rollback
from atlas.storage import Store


def make_client(tmp_path, trained, key="", faults=False):
    _, bundle = trained
    state = tmp_path / "registry.json"
    activate(state, bundle.path)
    app = create_app(state, tmp_path / "feedback.sqlite", api_key=key, allow_faults=faults)
    return TestClient(app), app


def test_api_contract_and_seen_filter(tmp_path, trained):
    client, app = make_client(tmp_path, trained)
    _, bundle = trained
    user = next(u for u, h in bundle.histories.items() if h["positive"])
    response = client.post("/recommend", json={"user_id": user, "algorithm": "ranked"})
    assert response.status_code == 200
    result = response.json()
    seen = {bundle.items[i]["item_id"] for i in bundle.histories[user]["seen"]}
    assert not seen & {x["item_id"] for x in result["recommendations"]}
    assert result["model_version"] == bundle.version
    assert "not a probability" in result["score_meaning"]
    assert client.get("/ready").json()["status"] == "ready"
    assert "atlas_requests_total" in client.get("/metrics").text


def test_unknown_user_fallback(tmp_path, trained):
    client, _ = make_client(tmp_path, trained)
    result = client.post("/recommend", json={"user_id": "new", "algorithm": "tower"}).json()
    assert result["fallback_reason"] == "no_positive_history"
    assert result["effective_algorithm"] == "popularity"
    assert result["recommendations"]


def test_preference_onboarding_and_category_filter(tmp_path, trained):
    client, _ = make_client(tmp_path, trained)
    result = client.post(
        "/recommend",
        json={
            "user_id": "new",
            "algorithm": "tower",
            "preferred_categories": ["audio"],
            "category_filter": "audio",
        },
    ).json()
    assert result["onboarding_preferences_used"]
    assert all(x["title"].startswith("audio") for x in result["recommendations"])


def test_als_onboarding_without_collaborative_signal_uses_content(tmp_path, trained):
    client, app = make_client(tmp_path, trained)
    bundle = next(iter(app.state.registry.bundles.values()))
    category = bundle.items[0]["category"]
    bundle.als_factors[0] = 0
    request = {"user_id": "new-cold-seed", "preferred_categories": [category]}
    response = client.post("/recommend", json={**request, "algorithm": "als"}).json()
    content = client.post("/recommend", json={**request, "algorithm": "content"}).json()
    assert response["fallback_reason"] == "als_no_signal"
    assert response["effective_algorithm"] == "content"
    assert response["onboarding_preferences_used"]
    assert [x["item_id"] for x in response["recommendations"]] == [
        x["item_id"] for x in content["recommendations"]
    ]
    assert any(x["score"] > 0 for x in response["recommendations"])


def test_invalid_request_and_auth(tmp_path, trained):
    client, _ = make_client(tmp_path, trained, key="test-key")
    assert client.post("/recommend", json={"user_id": "u"}).status_code == 401
    assert (
        client.post(
            "/recommend", headers={"X-API-Key": "test-key"}, json={"user_id": "u", "k": 100}
        ).status_code
        == 422
    )
    assert client.get("/health").status_code == 200


def test_feedback_idempotency_and_conflict(tmp_path, trained):
    client, _ = make_client(tmp_path, trained)
    result = client.post("/recommend", json={"user_id": "new"}).json()
    payload = {
        "event_id": "same-event",
        "request_id": result["request_id"],
        "item_id": result["recommendations"][0]["item_id"],
        "signal": "like",
    }
    assert client.post("/feedback", json=payload).json()["status"] == "recorded"
    assert client.post("/feedback", json=payload).json()["status"] == "duplicate"
    assert client.post("/feedback", json={**payload, "signal": "dislike"}).status_code == 409


def test_unexposed_and_load_test_feedback_rejected(tmp_path, trained):
    client, _ = make_client(tmp_path, trained)
    result = client.post("/recommend", json={"user_id": "new", "source": "load_test"}).json()
    payload = {
        "event_id": "x",
        "request_id": result["request_id"],
        "item_id": result["recommendations"][0]["item_id"],
        "signal": "like",
    }
    assert client.post("/feedback", json=payload).status_code == 409
    assert client.post("/feedback", json={**payload, "item_id": "never-exposed"}).status_code == 409


def test_retrieval_exception_fallback(tmp_path, trained):
    client, app = make_client(tmp_path, trained, faults=True)
    app.state.faults["primary"] = {"retrieval_error": True}
    result = client.post("/recommend", json={"user_id": "new", "algorithm": "ranked"}).json()
    assert result["fallback_reason"] == "retrieval_failure"
    assert result["recommendations"]


def test_bundle_corruption_cannot_activate(tmp_path, trained):
    _, bundle = trained
    copied = tmp_path / "corrupt"
    shutil.copytree(bundle.path, copied)
    (copied / "items.json").write_text("[]")
    state = tmp_path / "registry.json"
    activate(state, bundle.path)
    original = state.read_text()
    with pytest.raises(ValueError, match="checksum"):
        activate(state, copied)
    assert state.read_text() == original


def test_feature_schema_mismatch(tmp_path, trained):
    _, bundle = trained
    copied = tmp_path / "schema"
    shutil.copytree(bundle.path, copied)
    manifest = json.loads((copied / "bundle.json").read_text())
    manifest["feature_names"] = ["incorrect"]
    (copied / "bundle.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Feature schema"):
        Bundle(copied)


def test_canary_assignment_and_live_rollback(tmp_path, trained):
    _, bundle = trained
    copied = tmp_path / "candidate"
    shutil.copytree(bundle.path, copied)
    manifest = json.loads((copied / "bundle.json").read_text())
    manifest["version"] = "candidate"
    (copied / "bundle.json").write_text(json.dumps(manifest))
    state = tmp_path / "registry.json"
    activate(state, bundle.path)
    router = Registry(state)
    activate(state, copied, 50)
    user = next(f"u{i}" for i in range(100) if bucket(f"u{i}") < 5000)
    assert router.select(user)[0].version == "candidate"
    rollback(state)
    assert router.select(user)[0].version == bundle.version


def test_full_activation_rollback(tmp_path, trained):
    _, bundle = trained
    copied = tmp_path / "second"
    shutil.copytree(bundle.path, copied)
    state = tmp_path / "registry.json"
    activate(state, bundle.path)
    activate(state, copied)
    assert rollback(state)["primary"] == str(bundle.path)


def test_feedback_export_separated(tmp_path):
    store = Store(tmp_path / "data.sqlite")
    store.exposure("r", "u", "demo", "v1", "primary", ["item"])
    store.feedback({"event_id": "e", "request_id": "r", "item_id": "item", "signal": "like"})
    out = tmp_path / "feedback.jsonl"
    assert store.export(out)["rows"] == 1
    row = json.loads(out.read_text())
    assert row["source"] == "demo"
    assert row["user_key"] != "u"
