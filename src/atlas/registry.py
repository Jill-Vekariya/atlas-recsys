"""Atomic on-disk routing state; serving processes reload it on the next request."""

import hashlib
import json
import os
from pathlib import Path
from threading import RLock

from atlas.bundle import Bundle


def bucket(user_id: str, experiment: str = "atlas-v1") -> int:
    return int(hashlib.sha256(f"{experiment}:{user_id}".encode()).hexdigest()[:8], 16) % 10000


def write_state(path: str | Path, state: dict):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(state, indent=2))
    temporary.replace(path)


def activate(state_path, bundle_path, canary_percent=0):
    bundle = Bundle(bundle_path)  # Validate all assets BEFORE touching active state.
    path = Path(state_path)
    old = json.loads(path.read_text()) if path.exists() else None
    target = str(bundle.path)
    if not 0 <= canary_percent <= 100:
        raise ValueError("Canary percent must be in [0,100]")
    if canary_percent:
        if old is None:
            raise ValueError("Activate a primary bundle before starting a canary")
        state = {**old, "candidate": target, "canary_percent": canary_percent}
    else:
        state = {
            "primary": target,
            "previous": old["primary"] if old else None,
            "candidate": None,
            "canary_percent": 0,
        }
    write_state(path, state)
    return state


def rollback(state_path):
    path = Path(state_path)
    state = json.loads(path.read_text())
    if state.get("candidate"):
        state.update(candidate=None, canary_percent=0)
    elif state.get("previous"):
        Bundle(state["previous"])
        state["primary"], state["previous"] = state["previous"], state["primary"]
    else:
        raise ValueError("No candidate or previous bundle to roll back")
    write_state(path, state)
    return state


class Registry:
    def __init__(self, state_path):
        self.path = Path(state_path)
        self.lock = RLock()
        self.signature = None
        self.state = {}
        self.bundles = {}
        self.reload()

    def reload(self):
        signature = self.path.read_bytes()
        with self.lock:
            if signature == self.signature:
                return
            state = json.loads(signature)
            paths = [state["primary"]] + ([state["candidate"]] if state.get("candidate") else [])
            loaded = {p: self.bundles.get(p) or Bundle(p) for p in paths}
            self.state, self.bundles, self.signature = state, loaded, signature

    def select(self, user_id):
        self.reload()
        with self.lock:
            candidate = self.state.get("candidate")
            is_canary = bool(candidate and bucket(user_id) < self.state["canary_percent"] * 100)
            path = candidate if is_canary else self.state["primary"]
            return self.bundles[path], "canary" if is_canary else "primary"
