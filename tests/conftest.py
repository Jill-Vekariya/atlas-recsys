import copy

import pytest

from atlas.bundle import Bundle
from atlas.config import load_config
from atlas.data import prepare
from atlas.pipeline import train


@pytest.fixture(scope="session")
def trained(tmp_path_factory):
    root = tmp_path_factory.mktemp("atlas")
    cfg = copy.deepcopy(load_config("configs/smoke.yaml"))
    cfg.update(
        dataset_dir=str(root / "data"),
        bundle_dir=str(root / "bundle"),
        report_dir=str(root / "reports"),
        synthetic_users=20,
        synthetic_items=90,
        synthetic_events=1200,
        epochs=2,
        als_iterations=3,
        max_ranker_queries=30,
        max_eval_users=20,
        mlflow=False,
    )
    prepare(cfg)
    train(cfg)
    return cfg, Bundle(cfg["bundle_dir"])
