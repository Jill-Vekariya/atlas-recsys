"""Run the bounded Stage 4 study into a new, immutable output directory."""

import argparse
import json
from pathlib import Path

from atlas.config import load_config
from atlas.study import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/smoke.yaml"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(load_config(args.config), args.output)
    print(json.dumps(result["summary"], indent=2))
    if result["summary"]["failed_seeds"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
