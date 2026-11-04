"""Bounded multi-seed temporal study with a sealed selection phase before testing."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import statistics

COHORT_METRICS = (
    "ndcg_at_10",
    "returning_ndcg_at_10",
    "new_user_ndcg_at_10",
    "controlled_cold_recall_at_100",
    "head_recall_at_100",
    "low_history_recall_at_100",
    "zero_history_recall_at_100",
)


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)


def verify_dataset(directory, expected_manifest):
    directory = Path(directory)
    if file_hash(directory / "manifest.json") != expected_manifest:
        raise ValueError("Dataset manifest changed")
    manifest = json.loads((directory / "manifest.json").read_text())
    for name, expected in manifest["checksums"].items():
        path = (directory / name).resolve()
        if not path.is_relative_to(directory.resolve()) or file_hash(path) != expected:
            raise ValueError("Prepared dataset bytes changed")


def summarize(records, planned_seeds):
    if len(set(planned_seeds)) != len(planned_seeds):
        raise ValueError("Unique planned seeds required")
    if len({r["seed"] for r in records}) != len(records) or set(r["seed"] for r in records) - set(
        planned_seeds
    ):
        raise ValueError("Duplicate or unplanned seed")
    completed = [r for r in records if r["status"] == "evaluated"]
    metrics = {}
    for metric in COHORT_METRICS:
        differences = []
        for row in completed:
            scores = row["test"]["results"]
            selected = scores[row["selected_algorithm"]].get(metric)
            baseline = scores["popularity"].get(metric)
            if selected is not None and baseline is not None:
                differences.append(selected - baseline)
        interval = None
        if len(differences) >= 2:
            rng = random.Random(101)
            samples = sorted(
                statistics.mean(rng.choices(differences, k=len(differences))) for _ in range(2000)
            )
            interval = [samples[49], samples[1949]]
        metrics[metric] = {
            "eligible_seeds": len(differences),
            "seed_deltas": differences,
            "mean_delta": statistics.mean(differences) if differences else None,
            "exploratory_seed_bootstrap_95": interval,
            "negative_seeds": sum(d < 0 for d in differences),
        }
    return {
        "planned_seeds": list(planned_seeds),
        "evaluated_seeds": len(completed),
        "failed_seeds": [r["seed"] for r in records if r["status"] == "failed"],
        "not_evaluated_seeds": [
            s
            for s in planned_seeds
            if not any(r["seed"] == s and r["status"] == "evaluated" for r in records)
        ],
        "selected_minus_popularity": metrics,
        "uncertainty": "2000 seed-level bootstrap resamples; same fixed dataset/users across seeds. "
        "Does not include dataset, population or temporal-window uncertainty.",
        "claims": "Synthetic mechanism evidence only; no business uplift or production claim",
    }


def run(config, output, seeds=(17, 29, 41)):
    from atlas.bundle import Bundle
    from atlas.data import prepare, read_prepared
    from atlas.evaluation import evaluate
    from atlas.pipeline import train

    if (
        not 2 <= len(seeds) <= 5
        or len(set(seeds)) != len(seeds)
        or any(type(s) is not int or not 0 <= s < 2**31 for s in seeds)
    ):
        raise ValueError("Two to five distinct bounded integer training seeds required")
    if config["source"] != "synthetic":
        raise ValueError("Default study is synthetic and makes no network requests")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    base = deepcopy(config)
    base.update(
        dataset_dir=str(output / "dataset"), seed=20261029, evaluation_seed=101, mlflow=False
    )
    # Resource bounds are explicit and recorded before any preparation or training.
    base.update(
        synthetic_users=32,
        synthetic_items=120,
        synthetic_events=2400,
        epochs=2,
        als_iterations=3,
        ranker_trees=12,
        max_ranker_queries=40,
        max_eval_users=32,
        bootstrap_samples=100,
        threads=1,
    )
    protocol = {
        "schema_version": "stage4-temporal-study-v1",
        "config": base,
        "training_seeds": list(seeds),
        "selection_metric": "validation macro NDCG@10",
        "hypothesis": "Validation-selected models may fail to beat popularity on held-out temporal cohorts.",
        "comparison": "All existing algorithms, with popularity as the declared reference",
        "experimental_unit": "training seed on one fixed temporal dataset and fixed evaluation-user sample",
        "sample_size_rationale": "Three seeds default: bounded reproducibility/variance demonstration, not a powered model-quality claim",
        "stopping": "No failed seed replacement; retain each failure; never tune after test exposure",
        "final_evaluation": "Seal all validation selections before evaluating any test split",
    }
    write_new(output / "protocol.json", protocol)
    prepare(base)
    dataset_hash = file_hash(output / "dataset/manifest.json")
    records = []
    for seed in seeds:
        cfg = {
            **base,
            "seed": seed,
            "bundle_dir": str(output / f"seed-{seed}/bundle"),
            "report_dir": str(output / f"seed-{seed}/reports"),
        }
        row = {"seed": seed, "config": cfg, "status": "training"}
        try:
            verify_dataset(base["dataset_dir"], dataset_hash)
            result = train(cfg)
            row.update(
                status="selected",
                selected_algorithm=result["selected_algorithm"],
                validation_sha256=file_hash(Path(cfg["report_dir"]) / "validation.json"),
                bundle_sha256=file_hash(Path(cfg["bundle_dir"]) / "bundle.json"),
            )
        except Exception as exc:
            row.update(
                status="failed", phase="training", error_type=type(exc).__name__, error=str(exc)
            )
        records.append(row)
        write_new(output / f"seed-{seed}-selection.json", row)
    write_new(output / "selection-lock.json", {"dataset_sha256": dataset_hash, "records": records})
    lock_hash = file_hash(output / "selection-lock.json")
    for row in records:
        if row["status"] != "selected":
            continue
        try:
            cfg = row["config"]
            verify_dataset(base["dataset_dir"], dataset_hash)
            if (
                file_hash(output / "selection-lock.json") != lock_hash
                or file_hash(output / "dataset/manifest.json") != dataset_hash
                or file_hash(Path(cfg["bundle_dir"]) / "bundle.json") != row["bundle_sha256"]
                or file_hash(Path(cfg["report_dir"]) / "validation.json")
                != row["validation_sha256"]
            ):
                raise ValueError("Selection or dataset changed before final evaluation")
            _, events, _ = read_prepared(cfg)
            row["test"] = evaluate(Bundle(cfg["bundle_dir"]), events, cfg, "test")
            row["status"] = "evaluated"
        except Exception as exc:
            row.update(status="failed", phase="test", error_type=type(exc).__name__, error=str(exc))
        write_new(output / f"seed-{row['seed']}-outcome.json", row)
    result = {
        "selection_lock_sha256": lock_hash,
        "summary": summarize(records, seeds),
        "records": records,
    }
    write_new(output / "results.json", result)
    return result
