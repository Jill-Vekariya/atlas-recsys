"""Canonical data, deterministic catalog sampling, and temporal boundaries."""

import gzip
import hashlib
import json
import urllib.request
import zipfile
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from atlas.utils import sha256 as sha256


def stable_int(value: str) -> int:
    return int(hashlib.sha256(value.encode()).hexdigest()[:16], 16)


def download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return
    partial = target.with_suffix(target.suffix + ".part")
    try:
        with urllib.request.urlopen(url, timeout=60) as src, partial.open("wb") as dst:
            for chunk in iter(lambda: src.read(1024 * 1024), b""):
                dst.write(chunk)
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)


def synthetic(cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    rng = np.random.default_rng(cfg["seed"])
    n, u, m = cfg["synthetic_items"], cfg["synthetic_users"], cfg["synthetic_events"]
    categories = np.array(["audio", "fitness", "books", "kitchen", "outdoors", "gaming"])
    items = pd.DataFrame(
        {
            "item_id": [f"product-{i:04}" for i in range(n)],
            "title": [f"{categories[i % 6]} product {i}" for i in range(n)],
            "category": [categories[i % 6] for i in range(n)],
            "text": [
                f"{categories[i % 6]} useful {categories[i % 6]} equipment variant {i % 13}"
                for i in range(n)
            ],
        }
    )
    preferences = rng.integers(0, 6, u)
    rows = []
    for t in range(m):
        user = int(rng.integers(u))
        cat = int(preferences[user]) if rng.random() < 0.82 else int(rng.integers(6))
        item = int(rng.choice(np.arange(cat, n, 6)))
        rows.append(
            (
                f"demo-user-{user:03}",
                items.iloc[item].item_id,
                1700000000 + t * 120,
                5.0 if cat == preferences[user] else 2.0,
            )
        )
    return (
        items,
        pd.DataFrame(rows, columns=["user_id", "item_id", "timestamp", "rating"]),
        {
            "source": "synthetic",
            "synthetic": True,
            "warning": "Engineered category preference fixture; not real behavior or business evidence",
        },
    )


def movielens(cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    raw = Path(cfg["raw_dir"])
    path = raw / "ml-latest-small.zip"
    url = "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip"
    download(url, path)
    with zipfile.ZipFile(path) as z:
        movies = pd.read_csv(z.open("ml-latest-small/movies.csv"))
        ratings = pd.read_csv(z.open("ml-latest-small/ratings.csv"))
    items = pd.DataFrame(
        {
            "item_id": "movie-" + movies.movieId.astype(str),
            "title": movies.title,
            "category": movies.genres.str.split("|").str[0].fillna("unknown"),
            "text": movies.title + " " + movies.genres.str.replace("|", " ", regex=False),
        }
    )
    events = ratings.rename(columns={"userId": "user_id", "movieId": "item_id"})
    events["user_id"] = "ml-user-" + events.user_id.astype(str)
    events["item_id"] = "movie-" + events.item_id.astype(str)
    return (
        items,
        events[["user_id", "item_id", "timestamp", "rating"]],
        {
            "source": "movielens",
            "synthetic": False,
            "url": url,
            "raw_sha256": sha256(path),
            "warning": "Later catalog snapshot assumed available; timestamps describe ratings, not views",
        },
    )


def amazon(cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    category = cfg["category"]
    if not category.replace("_", "").isalnum():
        raise ValueError("Invalid category")
    raw = Path(cfg["raw_dir"])
    base = "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw"
    reviews = raw / f"{category}.jsonl.gz"
    meta = raw / f"meta_{category}.jsonl.gz"
    download(f"{base}/review_categories/{category}.jsonl.gz", reviews)
    download(f"{base}/meta_categories/meta_{category}.jsonl.gz", meta)
    catalog = []
    with gzip.open(meta, "rt") as f:
        for line in f:
            x = json.loads(line)
            item = x.get("parent_asin")
            if not item:
                continue
            cats = x.get("categories") or [x.get("main_category") or category]
            # Exclude average_rating, rating_number, review text, and price snapshot.
            text = " ".join(
                [
                    str(x.get("title") or ""),
                    str(x.get("description") or ""),
                    str(x.get("features") or ""),
                    str(cats),
                ]
            )
            catalog.append((item, str(x.get("title") or item), str(cats[-1]), text))
    items = pd.DataFrame(catalog, columns=["item_id", "title", "category", "text"])
    items = items.drop_duplicates("item_id")
    items["sampling_hash"] = items.item_id.map(stable_int)
    items = (
        items.sort_values("sampling_hash").head(cfg["catalog_limit"]).drop(columns="sampling_hash")
    )
    allowed = set(items.item_id)
    rows = []
    scanned = 0
    with gzip.open(reviews, "rt") as f:
        for line in f:
            scanned += 1
            x = json.loads(line)
            if x.get("parent_asin") in allowed:
                user = hashlib.sha256(str(x["user_id"]).encode()).hexdigest()[:20]
                rows.append(
                    (user, x["parent_asin"], int(x["timestamp"]) // 1000, float(x["rating"]))
                )
    return (
        items,
        pd.DataFrame(rows, columns=["user_id", "item_id", "timestamp", "rating"]),
        {
            "source": "amazon",
            "synthetic": False,
            "category": category,
            "raw_sha256": {reviews.name: sha256(reviews), meta.name: sha256(meta)},
            "raw_reviews_scanned": scanned,
            "catalog_sampling": "Lowest SHA256 item hashes from metadata, independent of review labels",
            "warning": "Later metadata snapshot assumed available; no actual product introduction times",
        },
    )


def validate(items: pd.DataFrame, events: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if items.empty or events.empty:
        raise ValueError("Dataset is empty")
    if (
        items.item_id.isna().any()
        or events[["user_id", "item_id", "timestamp", "rating"]].isna().any().any()
    ):
        raise ValueError("Missing identifiers, timestamps, or ratings")
    if not np.isfinite(events.rating).all() or not events.rating.between(0, 5).all():
        raise ValueError("Invalid ratings")
    if not np.isfinite(events.timestamp).all() or (events.timestamp <= 0).any():
        raise ValueError("Invalid timestamps")
    items = items.drop_duplicates("item_id").sort_values("item_id").reset_index(drop=True)
    items[["title", "category", "text"]] = items[["title", "category", "text"]].fillna("")
    events = events[events.item_id.isin(items.item_id)].copy()
    events = events.drop_duplicates(["user_id", "item_id", "timestamp", "rating"])
    events = events.sort_values(["timestamp", "user_id", "item_id"]).reset_index(drop=True)
    return items, events


def prepare(cfg: dict) -> dict:
    loaders = {"synthetic": synthetic, "amazon": amazon, "movielens": movielens}
    items, events, manifest = loaders[cfg["source"]](cfg)
    items, events = validate(items, events)
    times = events.timestamp.to_numpy()
    boundaries = [
        int(np.quantile(times, q))
        for q in (
            cfg["train_fraction"],
            cfg["train_fraction"] + cfg["ranker_fraction"],
            cfg["train_fraction"] + cfg["ranker_fraction"] + cfg["validation_fraction"],
        )
    ]
    if len(set(boundaries)) != 3:
        raise ValueError("Not enough distinct times for four temporal windows")
    a, b, c = boundaries
    cold = {
        i for i in items.item_id if stable_int(f"{cfg['seed']}:{i}") / 2**64 < cfg["cold_fraction"]
    }
    # Withhold all events for controlled cold items from BOTH supervised training windows.
    withheld = events.item_id.isin(cold) & (events.timestamp < b)
    withheld_count = int(withheld.sum())
    events = events[~withheld].copy()
    events["split"] = np.select(
        [events.timestamp < a, events.timestamp < b, events.timestamp < c],
        ["retriever", "ranker", "validation"],
        default="test",
    )
    items["controlled_cold"] = items.item_id.isin(cold)
    out = Path(cfg["dataset_dir"])
    out.mkdir(parents=True, exist_ok=True)
    items.to_parquet(out / "items.parquet", index=False)
    events.to_parquet(out / "events.parquet", index=False)
    manifest.update(
        {
            "items": len(items),
            "events": len(events),
            "users": events.user_id.nunique(),
            "boundaries": {"retriever_end": a, "ranker_end": b, "validation_end": c},
            "withheld_training_events": withheld_count,
            "controlled_cold_items": len(cold),
            "positive_rating": cfg["positive_rating"],
            "seed": cfg["seed"],
            "metadata_protocol": "Transductive catalog snapshot; text transforms fit on this catalog",
            "split_counts": {k: int(v) for k, v in events.split.value_counts().items()},
            "checksums": {p.name: sha256(p) for p in out.glob("*.parquet")},
        }
    )
    con = duckdb.connect()
    con.register("events", events)
    audit = con.execute(
        "SELECT split, count(*) AS n_events, count(DISTINCT user_id) AS n_users, "
        "avg(CASE WHEN rating >= ? THEN 1.0 ELSE 0.0 END) AS positive_share "
        "FROM events GROUP BY split ORDER BY split",
        [cfg["positive_rating"]],
    ).df()
    manifest["audit"] = audit.to_dict("records")
    con.close()
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def read_prepared(cfg: dict):
    d = Path(cfg["dataset_dir"])
    return (
        pd.read_parquet(d / "items.parquet"),
        pd.read_parquet(d / "events.parquet"),
        json.loads((d / "manifest.json").read_text()),
    )
