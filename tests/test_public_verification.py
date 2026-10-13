"""Public deployment checks must never transmit a locally configured API secret."""

from pathlib import Path

import httpx


def test_public_verification_does_not_send_credentials(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    import verify_public_endpoint

    secret = "local-secret-must-never-leave-this-process"
    monkeypatch.setenv("ATLAS_API_KEY", secret)
    requests = []

    def respond(request):
        requests.append(request)
        if request.url.path == "/api/ready":
            return httpx.Response(200, json={"status": "ready", "version": "v1", "synthetic": True})
        if request.url.path == "/api/openapi.json":
            return httpx.Response(200, json={"servers": [{"url": "/api"}]})
        if request.url.path == "/api/recommend":
            return httpx.Response(401)
        return httpx.Response(200, text="<html>Public demo</html>")

    original_client = httpx.Client
    monkeypatch.setattr(
        verify_public_endpoint.httpx,
        "Client",
        lambda **kwargs: original_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    monkeypatch.setattr(verify_public_endpoint, "websocket_upgrade", lambda _: None)
    assert verify_public_endpoint.verify_public("https://public.demo.example")["passed"]
    assert requests
    for request in requests:
        assert "x-api-key" not in request.headers
        assert "authorization" not in request.headers
        assert secret not in str(request.headers)
        assert secret.encode() not in request.content
