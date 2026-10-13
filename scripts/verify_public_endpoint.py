"""Check a public Atlas endpoint without reading or transmitting any API key."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

from verify_deployment import websocket_upgrade


def verify_public(base_url):
    checks = []
    with httpx.Client(base_url=base_url, timeout=30, trust_env=False) as client:
        ready = client.get("/api/ready")
        ready.raise_for_status()
        assert ready.json()["status"] == "ready"
        checks.append("Public API readiness")
        client.get("/_stcore/health").raise_for_status()
        page = client.get("/")
        page.raise_for_status()
        assert "<html" in page.text.lower()
        checks.append("Public Streamlit readiness and frontend HTML")
        schema = client.get("/api/openapi.json")
        schema.raise_for_status()
        assert {"url": "/api"} in schema.json()["servers"]
        client.get("/api/docs").raise_for_status()
        checks.append("Public Swagger and OpenAPI routing")
        response = client.post(
            "/api/recommend", json={"user_id": "public-auth-check", "source": "load_test"}
        )
        assert response.status_code == 401, "Public API must reject unauthenticated requests"
        checks.append("Public unauthenticated API rejection")
    websocket_upgrade(base_url)
    checks.append("Public Streamlit WebSocket upgrade")
    return {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "passed": True,
        "synthetic": ready.json()["synthetic"],
        "model_version": ready.json()["version"],
        "checks": checks,
        "scope": "Public checks without credentials; authenticated model/feedback checks run locally",
        "limitations": "No public load test or real-user quality experiment",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = json.dumps(verify_public(args.url.rstrip("/")), indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report)
    print(report, end="")
