"""Verify a running single-port Atlas deployment without exposing its API key."""

import argparse
import base64
import hashlib
import json
import os
import socket
import ssl
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx


def websocket_upgrade(base_url):
    url = urlsplit(base_url)
    port = url.port or (443 if url.scheme == "https" else 80)
    connection = socket.create_connection((url.hostname, port), timeout=15)
    if url.scheme == "https":
        connection = ssl.create_default_context().wrap_socket(
            connection, server_hostname=url.hostname
        )
    key = base64.b64encode(os.urandom(16)).decode()
    request = (
        f"GET {url.path.rstrip('/')}/_stcore/stream HTTP/1.1\r\n"
        f"Host: {url.netloc}\r\nOrigin: {url.scheme}://{url.netloc}\r\n"
        "Connection: Upgrade\r\nUpgrade: websocket\r\n"
        f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
        "Sec-WebSocket-Protocol: streamlit\r\n\r\n"
    )
    with connection:
        connection.sendall(request.encode())
        response = b""
        while b"\r\n\r\n" not in response and len(response) < 16384:
            part = connection.recv(4096)
            if not part:
                break
            response += part
    header = response.split(b"\r\n\r\n", 1)[0].decode()
    assert header.split("\r\n", 1)[0].split()[1] == "101", header
    expected = base64.b64encode(
        hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
    ).decode()
    headers = {
        name.lower(): value.strip()
        for name, value in (line.split(":", 1) for line in header.split("\r\n")[1:] if ":" in line)
    }
    assert headers.get("sec-websocket-accept") == expected, "Invalid WebSocket handshake"


def verify(base_url, api_key):
    checks = []
    with httpx.Client(base_url=base_url, timeout=20, trust_env=False) as client:
        ready = client.get("/api/ready")
        ready.raise_for_status()
        assert ready.json()["status"] == "ready"
        checks.append("API readiness")
        client.get("/_stcore/health").raise_for_status()
        frontend = client.get("/")
        frontend.raise_for_status()
        assert "<html" in frontend.text.lower()
        checks.append("Streamlit readiness and frontend HTML")
        schema = client.get("/api/openapi.json")
        schema.raise_for_status()
        assert {"url": "/api"} in schema.json()["servers"]
        client.get("/api/docs").raise_for_status()
        checks.append("Swagger and OpenAPI routing")
        payload = {
            "user_id": f"deployment-verifier-{uuid.uuid4()}",
            "source": "demo",
            "algorithm": "tower",
        }
        if api_key:
            assert client.post("/api/recommend", json=payload).status_code == 401
            checks.append("Unauthenticated API rejection")
            client.headers["X-API-Key"] = api_key
        response = client.post("/api/recommend", json=payload)
        response.raise_for_status()
        result = response.json()
        assert len(result["recommendations"]) == 10
        assert result["fallback_reason"] == "no_positive_history"
        checks.append("New-user recommendations and fallback")
        feedback = {
            "event_id": str(uuid.uuid4()),
            "request_id": result["request_id"],
            "item_id": result["recommendations"][0]["item_id"],
            "signal": "like",
        }
        for expected_status in ["recorded", "duplicate"]:
            response = client.post("/api/feedback", json=feedback)
            response.raise_for_status()
            assert response.json()["status"] == expected_status
        checks.append("Demo feedback and retry idempotency")
        metrics = client.get("/api/metrics")
        metrics.raise_for_status()
        assert "atlas_requests_total" in metrics.text
        checks.append("Authenticated monitoring")
    websocket_upgrade(base_url)
    checks.append("Streamlit WebSocket upgrade")
    return {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "passed": True,
        "synthetic": ready.json()["synthetic"],
        "model_version": ready.json()["version"],
        "checks": checks,
        "limitations": "Application smoke checks, not a load test or real-user quality experiment",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:10000")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify(args.url.rstrip("/"), os.getenv("ATLAS_API_KEY", ""))
    formatted = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(formatted)
    print(formatted, end="")
