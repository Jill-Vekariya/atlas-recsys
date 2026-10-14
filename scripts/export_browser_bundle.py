"""Export a verified synthetic model for browser inference and independent parity checks."""

import argparse
import json
from pathlib import Path

import numpy as np

from atlas.bundle import Bundle
from atlas.features import FEATURE_NAMES, fold_in_als, rank_features
from atlas.utils import sha256


def compact_tree(node):
    if "leaf_value" in node:
        return {"v": node["leaf_value"]}
    if node["decision_type"] != "<=" or node["missing_type"] != "None":
        raise ValueError("Browser export only supports finite numerical tree features")
    return {
        "f": node["split_feature"],
        "t": node["threshold"],
        "l": compact_tree(node["left_child"]),
        "r": compact_tree(node["right_child"]),
    }


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n")


def selection_evidence(validation: dict, test: dict, dataset: str) -> dict:
    """Expose the validation decision and held-out outcome without test-based selection."""
    if validation.get("split") != "validation" or test.get("split") != "test":
        raise ValueError("Expected chronological validation and test reports")
    if any(
        r.get("source") != dataset or r.get("synthetic") is not False for r in (validation, test)
    ):
        raise ValueError("Only matching real-data evaluation reports may be published")
    if validation.get("population", {}).get("prediction_cutoff", 0) >= test.get(
        "population", {}
    ).get("prediction_cutoff", 0):
        raise ValueError("Validation must precede test")
    vr, tr = validation["results"], test["results"]
    if set(vr) != set(tr) or not vr:
        raise ValueError("Validation/test algorithms must match")
    eligible = {
        name: row["ndcg_at_10"] for name, row in vr.items() if row.get("ndcg_at_10") is not None
    }
    if not eligible:
        raise ValueError("No eligible validation result")
    winner = max(eligible, key=eligible.get)
    recorded = validation.get("selected_algorithm")
    if recorded is not None and recorded != winner:
        raise ValueError("Recorded selection disagrees with validation result")
    baseline = tr["popularity"]["ndcg_at_10"]
    outcome = tr[winner]["ndcg_at_10"]
    return {
        "validation_selected": winner,
        "validation_users": validation["population"]["sampled_users"],
        "test_users": test["population"]["sampled_users"],
        "test_returning_users": tr["popularity"]["returning_users"],
        "test_cold_target_users": tr["popularity"]["cold_evaluation_users"],
        "selected_test_ndcg_at_10": outcome,
        "popularity_test_ndcg_at_10": baseline,
        "selected_minus_popularity_test_ndcg": outcome - baseline,
        "validation_metrics": {
            name: {
                "ndcg_at_10": row["ndcg_at_10"],
                "sequential_p95_ms": row["local_sequential_p95_ms"],
            }
            for name, row in vr.items()
        },
        "limitations": (
            "Only validation metrics may select a configuration. Sequential in-process "
            "p95 is not HTTP latency, not paired with throughput, and not a production SLA. "
            "Data use a later catalog snapshot; results are single-seed."
        ),
    }


def export(bundle_path, output, reports):
    bundle = Bundle(bundle_path)
    if bundle.manifest["dataset"].get("synthetic") is not True:
        raise ValueError("Only synthetic catalogs and user histories may be published in the demo")
    dump = bundle.ranker.dump_model() if bundle.ranker else None
    if dump and (dump["average_output"] or dump["num_tree_per_iteration"] != 1):
        raise ValueError("Unsupported boosting objective")
    model = {
        "schema_version": 1,
        "synthetic": True,
        "version": bundle.version,
        "source_bundle_sha256": sha256(bundle.path / "bundle.json"),
        "feature_names": FEATURE_NAMES,
        "history_size": bundle.config["history_size"],
        "default_algorithm": bundle.manifest["default_algorithm"],
        "items": bundle.items,
        "histories": bundle.histories,
        "trees": [compact_tree(t["tree_structure"]) for t in dump["tree_info"]] if dump else [],
        "als_gram": bundle.als_gram.tolist(),
        **{
            key: getattr(bundle, key).tolist()
            for key in ["content", "vectors", "user_weights", "als_factors", "popularity"]
        },
    }
    write_json(output / "model.json", model)
    profiles = [h["positive"] for _, h in sorted(bundle.histories.items()) if h["positive"]][:12]
    profiles += [[], [0], [0, 2, 7, 159], [1, 1, 1, 5, 5, 2]]
    fixtures = []
    for history in profiles:
        query = bundle.query_vector(history)[0]
        retrieval = bundle.vectors @ query
        features = rank_features(
            np.arange(len(bundle.items)),
            retrieval,
            history,
            bundle.content,
            bundle.popularity,
            bundle.categories,
            bundle.config["history_size"],
        )
        als_query = fold_in_als(history, bundle.als_factors, gram=bundle.als_gram)
        fixtures.append(
            {
                "history": history,
                "query_vector": query.tolist(),
                "tower_scores": retrieval.tolist(),
                "als_scores": (bundle.als_factors @ als_query).tolist(),
                "features": features.tolist(),
                "ranker_scores": bundle.ranker.predict(features).tolist() if bundle.ranker else [],
            }
        )
    write_json(output / "tests" / "parity.json", {"fixtures": fixtures})
    evidence = {}
    for dataset in ["movielens", "amazon"]:
        validation = json.loads((reports / dataset / "validation.json").read_text())
        test = json.loads((reports / dataset / "test.json").read_text())
        manifest = json.loads((reports / dataset / "data_manifest.json").read_text())
        if manifest.get("source") != dataset:
            raise ValueError("Dataset manifest does not match evaluation")
        evidence[dataset] = {
            "source": dataset,
            "synthetic": test["synthetic"],
            "population": test["population"],
            "catalog_size": manifest["items"],
            "results": test["results"],
            "selection": selection_evidence(validation, test, dataset),
        }
    evidence["http_load"] = json.loads((reports / "movielens" / "http_load.json").read_text())
    write_json(output / "evidence.json", evidence)
    print(
        json.dumps(
            {
                "items": len(bundle.items),
                "trees": len(model["trees"]),
                "parity_profiles": len(fixtures),
                "model_bytes": (output / "model.json").stat().st_size,
                "source_bundle_sha256": model["source_bundle_sha256"],
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=Path("artifacts/synthetic-v1"))
    parser.add_argument("--output", type=Path, default=Path("web"))
    parser.add_argument("--reports", type=Path, default=Path("reports"))
    args = parser.parse_args()
    export(args.bundle, args.output, args.reports)
