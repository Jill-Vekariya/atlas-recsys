"""Idempotent container initialization. Never overwrites an existing model bundle."""

from pathlib import Path

from atlas.bundle import Bundle
from atlas.config import load_config
from atlas.data import prepare
from atlas.pipeline import train
from atlas.registry import activate

cfg = load_config("configs/smoke.yaml")
bundle = Path(cfg["bundle_dir"])
if not (bundle / "bundle.json").exists():
    prepare(cfg)
    train(cfg)
Bundle(bundle)
state = Path("artifacts/registry.json")
if not state.exists():
    activate(state, bundle)
print("Atlas synthetic demo bundle initialized. Real-data experiments are separate.")
