import argparse
import asyncio
import json
from pathlib import Path

from atlas.config import load_config


def main():
    parser = argparse.ArgumentParser(description="Atlas recommendation lab")
    parser.add_argument(
        "command",
        choices=[
            "prepare",
            "train",
            "evaluate",
            "tradeoffs",
            "smoke",
            "serve",
            "activate",
            "rollback",
            "inspect",
            "load-test",
            "canary-demo",
            "export-feedback",
            "ablations",
            "verify-local",
        ],
    )
    parser.add_argument("--config", default="configs/smoke.yaml")
    parser.add_argument("--state", default="artifacts/registry.json")
    parser.add_argument("--bundle")
    parser.add_argument("--split", choices=["validation", "test"], default="test")
    parser.add_argument("--canary-percent", type=float, default=0)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--rate", type=float, default=50)
    parser.add_argument("--duration", type=float, default=10)
    parser.add_argument("--output")
    parser.add_argument("--db", default="artifacts/feedback.sqlite")
    parser.add_argument("--check-ui", action="store_true")
    args = parser.parse_args()
    cfg = load_config(args.config)
    bundle_path = args.bundle or cfg["bundle_dir"]
    result = None
    if args.command in ("prepare", "smoke"):
        from atlas.data import prepare

        result = prepare(cfg)
        if args.command == "smoke":
            print(json.dumps({"prepared": {k: result[k] for k in ("source", "items", "events")}}))
    if args.command in ("train", "smoke"):
        from atlas.pipeline import train

        result = train(cfg)
    if args.command in ("evaluate", "tradeoffs", "smoke"):
        from atlas.bundle import Bundle
        from atlas.data import read_prepared
        from atlas.evaluation import evaluate, tradeoffs

        _, events, _ = read_prepared(cfg)
        bundle = Bundle(bundle_path)
        result = (
            tradeoffs(bundle, events, cfg)
            if args.command == "tradeoffs"
            else evaluate(bundle, events, cfg, args.split)
        )
    if args.command in ("activate", "smoke"):
        from atlas.registry import activate

        result = activate(args.state, bundle_path, args.canary_percent)
    elif args.command == "rollback":
        from atlas.registry import rollback

        result = rollback(args.state)
    elif args.command == "inspect":
        from atlas.bundle import Bundle

        result = Bundle(bundle_path).manifest
    elif args.command == "serve":
        import uvicorn
        from atlas.api import create_app

        uvicorn.run(
            create_app(args.state, args.db), host=args.host, port=args.port, log_level="info"
        )
    elif args.command in ("load-test", "verify-local"):
        from atlas.benchmark import load_test, verify_local

        if args.rate <= 0 or args.duration <= 0 or args.rate * args.duration > 100000:
            parser.error("Use a positive rate/duration and at most 100000 requests")
        output = args.output or str(Path(cfg["report_dir"]) / "http_load.json")
        result = (
            verify_local(bundle_path, output, args.rate, args.duration, args.check_ui)
            if args.command == "verify-local"
            else asyncio.run(load_test(args.url, bundle_path, output, args.rate, args.duration))
        )
    elif args.command == "canary-demo":
        from atlas.benchmark import canary_demo

        result = canary_demo(
            bundle_path, args.output or str(Path(cfg["report_dir"]) / "canary.json")
        )
    elif args.command == "export-feedback":
        from atlas.storage import Store

        result = Store(args.db).export(args.output or "data/feedback/export.jsonl")
    elif args.command == "ablations":
        from atlas.pipeline import train

        results = {}
        for variant in ["content_only", "identity_only"]:
            experiment = {
                **cfg,
                "item_variant": variant,
                "bundle_dir": cfg["bundle_dir"] + "-" + variant,
                "report_dir": str(Path(cfg["report_dir"]) / variant),
                "mlflow": False,
            }
            results[variant] = train(experiment)
        result = {
            "split": "validation_only",
            "item_representation_ablations": results,
            "note": "User tower still uses historical item content in every variant",
        }
        (Path(cfg["report_dir"]) / "ablations.json").write_text(json.dumps(result, indent=2))
    if result is not None:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
