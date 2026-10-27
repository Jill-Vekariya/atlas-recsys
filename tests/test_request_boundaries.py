import asyncio
import pytest
from atlas.middleware import BodyLimitMiddleware


def test_chunked_oversize_is_rejected_before_application():
    async def run():
        called = False
        sent = []

        async def app(scope, receive, send):
            nonlocal called
            called = True

        chunks = iter(
            [
                {"type": "http.request", "body": b"x" * 40_000, "more_body": True},
                {"type": "http.request", "body": b"x" * 40_000, "more_body": False},
            ]
        )

        async def receive():
            return next(chunks)

        async def send(value):
            sent.append(value)

        await BodyLimitMiddleware(app)(
            {"type": "http", "headers": [(b"content-length", b"1")]}, receive, send
        )
        assert not called and sent[0]["status"] == 413

    asyncio.run(run())


def test_valid_body_is_replayed_once_without_corruption():
    async def run():
        seen = []

        async def app(scope, receive, send):
            seen.append(await receive())

        chunks = iter(
            [
                {"type": "http.request", "body": b'{"a":', "more_body": True},
                {"type": "http.request", "body": b"1}", "more_body": False},
            ]
        )

        async def receive():
            return next(chunks)

        async def send(value):
            raise AssertionError("Middleware must not send a response")

        await BodyLimitMiddleware(app)({"type": "http"}, receive, send)
        assert seen == [{"type": "http.request", "body": b'{"a":1}', "more_body": False}]

    asyncio.run(run())


def test_production_rejects_missing_key_before_loading_artifacts(monkeypatch, tmp_path):
    from atlas.api import create_app, RecommendRequest
    from pydantic import ValidationError

    monkeypatch.setenv("ATLAS_ENV", "production")
    with pytest.raises(ValueError, match="Production requires"):
        create_app(tmp_path / "missing-state.json", tmp_path / "must-not-exist.sqlite", api_key="")
    assert not (tmp_path / "must-not-exist.sqlite").exists()
    with pytest.raises(ValidationError):
        RecommendRequest(user_id="u", preferred_categories=["x" * 101])
