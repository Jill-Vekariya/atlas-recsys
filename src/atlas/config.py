from pathlib import Path

import yaml


def load_config(path: str | Path) -> dict:
    cfg = yaml.safe_load(Path(path).read_text())
    if not isinstance(cfg, dict):
        raise ValueError("Config must be a mapping")
    fractions = [cfg[x] for x in ("train_fraction", "ranker_fraction", "validation_fraction")]
    if any(x <= 0 for x in fractions) or sum(fractions) >= 1:
        raise ValueError("Temporal fractions must be positive and sum to less than one")
    if not 0 <= cfg["cold_fraction"] < 1:
        raise ValueError("cold_fraction must be in [0, 1)")
    return cfg
