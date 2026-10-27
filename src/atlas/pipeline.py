"""Train A-window retrieval, B-window ranking, then select using validation only."""

import json
import platform
import time
from pathlib import Path

import faiss
import joblib
import lightgbm as lgb
import numpy as np
import torch

from atlas.bundle import Bundle
from atlas.data import read_prepared, sha256, stable_int
from atlas.evaluation import evaluate, tradeoffs
from atlas.features import FEATURE_NAMES, fit_content, histories, rank_features
from atlas.models import train_als, train_tower
from atlas.reports import write_new_report


def write_manifest(out, cfg, dataset, training, version):
    assets = {p.name: sha256(p) for p in out.iterdir() if p.is_file() and p.name != "bundle.json"}
    manifest = {
        "schema_version": 1,
        "version": version,
        "feature_names": FEATURE_NAMES,
        "config": cfg,
        "dataset": dataset,
        "training": training,
        "assets": assets,
        "default_algorithm": "ranked",
        "selection_status": "not_yet_validated",
    }
    (out / "bundle.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def train(cfg: dict):
    start = time.perf_counter()
    report_dir = Path(cfg["report_dir"])
    if report_dir.exists() and any(report_dir.iterdir()):
        raise ValueError("Reports already exist. Choose a new report_dir to retain prior evidence.")
    items, events, dataset = read_prepared(cfg)
    out = Path(cfg["bundle_dir"])
    if out.exists() and (out / "bundle.json").exists():
        raise ValueError("Bundle already exists. Choose a new bundle_dir; bundles are immutable.")
    out.mkdir(parents=True, exist_ok=True)
    item_map = {v: i for i, v in enumerate(items.item_id)}
    content, vectorizer, svd = fit_content(items, cfg["content_dim"], cfg["seed"])
    positive_a = events[(events.split == "retriever") & (events.rating >= cfg["positive_rating"])]
    popularity = np.zeros(len(items), dtype=np.float32)
    for item in positive_a.item_id:
        popularity[item_map[item]] += 1
    model, vectors, tower_info = train_tower(events, item_map, content, popularity, cfg)
    als_factors, als_info = train_als(events, item_map, cfg)
    np.savez_compressed(
        out / "arrays.npz",
        content=content,
        vectors=vectors,
        user_weights=model.user.weight.detach().numpy(),
        als_factors=als_factors,
        popularity=popularity,
    )
    torch.save(model.state_dict(), out / "tower.pt")
    joblib.dump({"vectorizer": vectorizer, "svd": svd}, out / "text_transform.joblib")
    faiss.omp_set_num_threads(cfg["threads"])
    exact = faiss.IndexFlatIP(vectors.shape[1])
    exact.add(vectors)
    hnsw = faiss.IndexHNSWFlat(vectors.shape[1], 16, faiss.METRIC_INNER_PRODUCT)
    hnsw.hnsw.efConstruction = 80
    hnsw.hnsw.efSearch = 64
    hnsw.add(vectors)
    faiss.write_index(exact, str(out / "exact.faiss"))
    faiss.write_index(hnsw, str(out / "hnsw.faiss"))
    (out / "items.json").write_text(items.to_json(orient="records"))
    online_hist = histories(
        events, item_map, dataset["boundaries"]["validation_end"], cfg["positive_rating"]
    )
    (out / "histories.json").write_text(json.dumps(online_hist))
    info = {"tower": tower_info, "als": als_info, "ranker": {"status": "pending"}}
    version = out.name
    write_manifest(out, cfg, dataset, info, version)
    bundle = Bundle(out)
    a_hist = histories(
        events, item_map, dataset["boundaries"]["retriever_end"], cfg["positive_rating"]
    )
    b_positive = events[(events.split == "ranker") & (events.rating >= cfg["positive_rating"])]
    groups = list(b_positive.groupby("user_id", sort=True))
    groups.sort(key=lambda g: stable_int(str(g[0]) + str(cfg["seed"])))
    rows, labels, sizes = [], [], []
    queries_without_retrieved_positive = 0
    for user, target in groups[: cfg["max_ranker_queries"]]:
        state = a_hist.get(str(user), {"positive": [], "seen": []})
        truth = {item_map[i] for i in target.item_id} - set(state["seen"])
        ids, scores, _, _ = bundle.candidates(
            state["positive"], state["seen"], cfg["candidate_count"], "tower"
        )
        y = np.array([int(i in truth) for i in ids])
        if len(ids) < 2 or y.sum() == 0 or y.sum() == len(y):
            queries_without_retrieved_positive += 1
            continue
        x = rank_features(
            ids,
            scores,
            state["positive"],
            content,
            popularity,
            bundle.categories,
            cfg["history_size"],
        )
        rows.append(x)
        labels.append(y)
        sizes.append(len(ids))
    info["ranker"] = {
        "training_queries": len(sizes),
        "excluded_uninformative_queries": queries_without_retrieved_positive,
        "protocol": "Frozen A retriever, A histories/features, B targets; no forced positive injection",
    }
    if sizes:
        ranker = lgb.LGBMRanker(
            objective="lambdarank",
            n_estimators=cfg["ranker_trees"],
            num_leaves=15,
            max_depth=5,
            learning_rate=0.05,
            min_child_samples=20,
            random_state=cfg["seed"],
            n_jobs=cfg["threads"],
            verbosity=-1,
        )
        ranker.fit(
            np.concatenate(rows), np.concatenate(labels), group=sizes, feature_name=FEATURE_NAMES
        )
        ranker.booster_.save_model(str(out / "ranker.txt"))
        info["ranker"]["status"] = "trained"
    else:
        info["ranker"]["status"] = "no_informative_candidate_groups"
    info["training_seconds"] = time.perf_counter() - start
    info["hardware"] = {
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "training_device": "CPU",
    }
    write_manifest(out, cfg, dataset, info, version)
    bundle = Bundle(out)
    validation = evaluate(bundle, events, cfg, "validation", write=False)
    available = {k: v for k, v in validation["results"].items() if v["ndcg_at_10"] is not None}
    winner = max(available, key=lambda k: available[k]["ndcg_at_10"]) if available else "popularity"
    manifest = json.loads((out / "bundle.json").read_text())
    manifest["default_algorithm"] = winner
    manifest["selection_status"] = "Selected by validation macro NDCG@10; no test-based tuning"
    (out / "bundle.json").write_text(json.dumps(manifest, indent=2))
    validation["selected_algorithm"] = winner
    write_new_report(report_dir / "validation.json", validation)
    tradeoffs(bundle, events, cfg)
    tracking = {"enabled": cfg.get("mlflow", False)}
    if cfg.get("mlflow"):
        try:
            import os

            os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"
            import mlflow

            mlflow.set_tracking_uri(Path("mlruns").resolve().as_uri())
            mlflow.set_experiment("atlas-cold-start")
            with mlflow.start_run(run_name=version):
                mlflow.log_params(
                    {k: v for k, v in cfg.items() if isinstance(v, (str, int, float, bool))}
                )
                for name, result in validation["results"].items():
                    for key in ["ndcg_at_10", "recall_at_100"]:
                        if result[key] is not None:
                            mlflow.log_metric(f"{name}_{key}", result[key])
                mlflow.log_artifact(str(Path(cfg["report_dir"]) / "validation.json"))
                tracking["run_id"] = mlflow.active_run().info.run_id
            tracking["status"] = "logged"
        except Exception as exc:
            tracking["status"] = "unavailable"
            tracking["error"] = str(exc)
    write_new_report(report_dir / "training.json", {**info, "mlflow": tracking})
    return {"bundle": str(out), "selected_algorithm": winner, **info, "mlflow": tracking}
