"""Retain experiment outputs rather than replacing an earlier measurement."""

import json
from pathlib import Path


def write_new_report(path, report):
    payload = json.dumps(report, indent=2)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(payload)
