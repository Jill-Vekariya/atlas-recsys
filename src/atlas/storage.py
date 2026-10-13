"""Exposure/feedback separation with idempotency and referential validation."""

import hashlib
import json
import sqlite3
import time
from pathlib import Path


def user_key(user_id):
    return hashlib.sha256(user_id.encode()).hexdigest()


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript("""
                CREATE TABLE IF NOT EXISTS exposures (
                    request_id TEXT PRIMARY KEY, user_key TEXT NOT NULL,
                    source TEXT NOT NULL, version TEXT NOT NULL, experiment TEXT NOT NULL,
                    items_json TEXT NOT NULL, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS feedback (
                    event_id TEXT PRIMARY KEY, request_id TEXT NOT NULL,
                    payload TEXT NOT NULL, created REAL NOT NULL,
                    FOREIGN KEY(request_id) REFERENCES exposures(request_id));
            """)

    def connect(self):
        c = sqlite3.connect(self.path, timeout=10)
        c.execute("PRAGMA foreign_keys=ON")
        return c

    def exposure(self, request_id, user_id, source, version, slot, items):
        with self.connect() as c:
            c.execute(
                "INSERT INTO exposures VALUES (?,?,?,?,?,?,?)",
                (
                    request_id,
                    user_key(user_id),
                    source,
                    version,
                    slot,
                    json.dumps(items),
                    time.time(),
                ),
            )

    def feedback(self, data):
        canonical = json.dumps(data, sort_keys=True)
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            existing = c.execute(
                "SELECT payload FROM feedback WHERE event_id=?", (data["event_id"],)
            ).fetchone()
            if existing:
                if existing[0] != canonical:
                    raise ValueError("Event ID already belongs to different feedback")
                return False
            exposure = c.execute(
                "SELECT items_json, source FROM exposures WHERE request_id=?", (data["request_id"],)
            ).fetchone()
            if exposure is None or data["item_id"] not in json.loads(exposure[0]):
                raise ValueError("Feedback must refer to an exposed item")
            if exposure[1] == "load_test":
                raise ValueError("Load-test traffic cannot enter the feedback dataset")
            c.execute(
                "INSERT INTO feedback VALUES (?,?,?,?)",
                (data["event_id"], data["request_id"], canonical, time.time()),
            )
            return True

    def export(self, target):
        with self.connect() as c:
            rows = c.execute(
                "SELECT e.user_key,e.source,e.version,e.experiment,f.payload,f.created "
                "FROM feedback f JOIN exposures e USING(request_id) "
                "ORDER BY f.created,f.event_id"
            ).fetchall()
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        with Path(target).open("w") as f:
            for key, source, version, slot, payload, created in rows:
                f.write(
                    json.dumps(
                        {
                            "user_key": key,
                            "source": source,
                            "model_version": version,
                            "experiment_slot": slot,
                            "feedback": json.loads(payload),
                            "timestamp": created,
                        }
                    )
                    + "\n"
                )
        return {"rows": len(rows), "path": str(target)}
