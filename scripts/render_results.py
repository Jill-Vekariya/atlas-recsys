"""Generate a human-readable summary from actual recorded numeric reports."""

import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
lines = [
    "# Recorded results",
    "",
    "These are observed runs, not promised future performance.",
    "",
    "Model selection used validation only. Catalog text is a later snapshot. One seed was run.",
    "",
]

for source in ["amazon", "movielens", "synthetic"]:
    folder = root / "reports" / source
    path = folder / "test.json"
    if not path.exists():
        continue
    report = json.loads(path.read_text())
    validation = json.loads((folder / "validation.json").read_text())
    training = json.loads((folder / "training.json").read_text())
    lines += [
        f"## {source.title()}",
        "",
        f"Synthetic: **{report['synthetic']}**. Test users: {report['population']['sampled_users']} "
        f"of {report['population']['eligible_users']} eligible users.",
        "",
        "| Algorithm | Recall@100 | NDCG@10 | Coverage@10 | Returning-user NDCG@10 | Cold Recall@100 |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    def fmt(x):
        return "n/a" if x is None else f"{x:.4f}"

    for name, m in report["results"].items():
        lines.append(
            f"| {name} | {fmt(m['recall_at_100'])} | {fmt(m['ndcg_at_10'])} | "
            f"{fmt(m['catalog_coverage_at_10'])} | {fmt(m['returning_ndcg_at_10'])} | "
            f"{fmt(m['controlled_cold_recall_at_100'])} |"
        )
    sample = report["results"]["tower"]
    lines += [
        "",
        f"Returning users with positive pre-cutoff history: **{sample['returning_users']}**.",
        f"Users with controlled-cold eligible targets: **{sample['cold_evaluation_users']}**.",
        f"Personalized retriever training examples: **{training['tower']['examples']}**.",
        "",
    ]
    winner = max(validation["results"], key=lambda x: validation["results"][x]["ndcg_at_10"] or 0)
    lines += [f"Validation-selected default: **{winner}**. It was not reselected on test.", ""]
    for name, interval in report["paired_comparisons"].items():
        if interval:
            low, high = interval["ci95"]
            lines.append(
                f"- {name}: absolute NDCG delta {interval['mean_delta']:.5f}; "
                f"paired user bootstrap 95% interval [{low:.5f}, {high:.5f}]."
            )
    lines += [""]

lines += [
    "## Interpretation",
    "",
    "The sampled Amazon category provides very little repeat-user history. Its personalized "
    "models receive too few training examples, and popularity fallback dominates evaluation. "
    "This is evidence about this sampled workload, not evidence that recommendation systems fail.",
    "",
    "MovieLens supplies more historical interactions, but the global temporal split still creates "
    "many new users. The validation-selected tower loses to popularity on final-test NDCG. "
    "The ranker also loses to ALS in this run. Retain these results: a complex model is not "
    "automatically the best serving policy. Do not tune repeatedly against the same final test.",
    "",
    "The hybrid tower has nonzero controlled-cold recall while popularity and ALS have zero in "
    "the MovieLens run. That specialized benefit is small and does not establish overall "
    "superiority. Check returning-user counts and uncertainty before claiming improvement.",
    "",
    "The synthetic fixture intentionally has a strong category signal. Its results validate "
    "the mechanics and cold-start paths rather than a real business hypothesis.",
    "",
]

for source in ["movielens", "synthetic"]:
    path = root / "reports" / source / "http_load.json"
    if not path.exists():
        continue
    r = json.loads(path.read_text())
    lines += [
        f"## {source.title()} HTTP benchmark",
        "",
        f"Catalog: {r['catalog_size']:,} items; {r['requests']} requests over "
        f"{r['requested_duration_seconds']:.0f} seconds, after {r['warmup_requests']} warmup requests.",
        "",
        "| Metric | Observed |",
        "|---|---:|",
        f"| Target arrival rate | {r['target_rps']:.1f} requests/s |",
        f"| Achieved successful throughput | {r['achieved_rps']:.2f} requests/s |",
        f"| p50 | {r['p50_ms']:.2f} ms |",
        f"| p95 | {r['p95_ms']:.2f} ms |",
        f"| p99 | {r['p99_ms']:.2f} ms |",
        f"| Request error rate | {r['error_rate']:.2%} |",
        f"| Fallback rate | {r['fallback_rate']:.2%} |",
        "",
        f"{r['measurement']}. {r['user_mix']}. {r['limitations']}.",
        "",
        "Fallback includes expected new-user responses. It does not imply the same proportion "
        "of service failures. Response caching is disabled; models and indexes are resident in RAM.",
        "",
    ]

path = root / "reports/synthetic/canary.json"
if path.exists():
    r = json.loads(path.read_text())
    lines += [
        "## Rollback demonstration",
        "",
        f"{r['traffic']}.",
        "",
        f"Injected condition: {r['injection']}. Guard: {r['guard']}.",
        "",
        f"Rollback triggered: **{r['rollback_triggered']}**. Post-rollback route: "
        f"**{r['post_rollback_slot']}**, bundle **{r['post_rollback_version']}**.",
        "",
    ]

lines += [
    "## Verification boundaries",
    "",
    "Python dependency installation, unit/integration checks, real HTTP requests, and "
    "Streamlit application flows were exercised. Docker, GitHub Actions, GHCR publication, "
    "and public hosting were not run in this environment. No online business A/B test, "
    "multi-node scaling test, or internship outcome is established.",
    "",
]
(root / "docs/RESULTS.md").write_text("\n".join(lines))
print("Wrote docs/RESULTS.md from recorded JSON reports")
