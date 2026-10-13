"""Run a self-contained demonstration on hosts exposing a single container port.

The synthetic bundle is built into the image. No training or dataset download occurs
on application startup. This small demo supervisor stops all children on shutdown/failure.
Docker Compose remains the preferred separate-service deployment for a persistent VM.
"""

import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def main():
    from atlas.bundle import Bundle
    from atlas.registry import activate

    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    bundle = Path(os.getenv("ATLAS_DEMO_BUNDLE", "artifacts/synthetic-v1"))
    Bundle(bundle)
    state = Path(os.getenv("ATLAS_STATE", "artifacts/registry.json"))
    activate(state, bundle)
    env = dict(os.environ)
    env.update(
        ATLAS_API_URL="http://127.0.0.1:8000",
        ATLAS_ROOT_PATH="/api",
        ATLAS_STATE=str(state.resolve()),
        ATLAS_DEMO_BUNDLE=str(bundle.resolve()),
    )
    env.setdefault("PORT", "10000")
    env.setdefault("OMP_NUM_THREADS", "1")
    env.setdefault("OPENBLAS_NUM_THREADS", "1")
    commands = [
        [
            sys.executable,
            "-m",
            "atlas.cli",
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
            "--state",
            str(state.resolve()),
            "--db",
            env.get("ATLAS_DB", "artifacts/feedback.sqlite"),
        ],
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "src/atlas/ui.py",
            "--server.address=127.0.0.1",
            "--server.port=8501",
            "--browser.gatherUsageStats=false",
        ],
        [
            env.get("ATLAS_CADDY_BIN", "/usr/local/bin/caddy"),
            "run",
            "--config",
            "deploy/Caddyfile.cloud",
            "--adapter",
            "caddyfile",
        ],
    ]
    children = []
    stopping = False

    def stop(_signum=None, _frame=None):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        for command in commands:
            children.append(subprocess.Popen(command, env=env))
        while not stopping:
            for child in children:
                if child.poll() is not None:
                    raise RuntimeError(
                        f"Demo process exited unexpectedly with code {child.returncode}"
                    )
            time.sleep(0.2)
        return 0
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        deadline = time.monotonic() + 8
        for child in children:
            try:
                child.wait(timeout=max(0.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


def health():
    port = os.getenv("PORT", "10000")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for path in ["/api/ready", "/_stcore/health"]:
        with opener.open(f"http://127.0.0.1:{port}{path}", timeout=4) as response:
            if response.status != 200:
                raise RuntimeError("Demo is not ready")


if __name__ == "__main__":
    if "--healthcheck" in sys.argv:
        health()
    else:
        raise SystemExit(main())
