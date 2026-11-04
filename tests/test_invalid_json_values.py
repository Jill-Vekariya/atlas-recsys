import pytest
from fastapi.testclient import TestClient

from atlas.api import create_app
from atlas.registry import activate


@pytest.mark.parametrize("number", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_json_returns_validation_error(tmp_path, trained, number):
    _, bundle = trained
    state = tmp_path / "routing.json"
    activate(state, bundle.path)
    with TestClient(create_app(state, tmp_path / "feedback.db")) as client:
        response = client.post(
            "/recommend",
            content='{"user_id":"private-input", "k":' + number + "}",
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "k"]
    assert "input" not in response.json()["detail"][0]


def test_non_ascii_api_key_returns_unauthorized(tmp_path, trained):
    _, bundle = trained
    state = tmp_path / "routing.json"
    activate(state, bundle.path)
    with TestClient(create_app(state, tmp_path / "feedback.db", api_key="test-key")) as client:
        response = client.post("/recommend", json={"user_id": "u"}, headers={b"X-API-Key": b"\xff"})
    assert response.status_code == 401
