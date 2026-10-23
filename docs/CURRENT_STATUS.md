# Current status

Updated 2026-10-23 for the cleanup review. The public Pages lab performs browser inference over a synthetic catalog. Python/Docker additionally provides the API, FAISS, feedback persistence, monitoring and rollout/rollback. The two deployment modes are separate.

## Run and verify

Follow the root README's frozen Python setup and run the synthetic smoke workflow once on a clean clone. The configured bundle is immutable: use a new config with new bundle/report paths for another experiment. `python scripts/check_links.py` checks local Markdown targets; `--online` also reports external reachability. Model/data experiments need the resources and source terms described in the [data card](DATA_CARD.md).

## Evidence and remaining work

The validation-selected MovieLens model lost to popularity on final test. The recorded Windows synthetic test met 150 ms p95 at 5 RPS and missed the 50 RPS target. Keep both results: see [the final engineering verification](FINAL_ENGINEERING_VERIFICATION.md). Neither a latency SLA nor business uplift is established. Extra seeds, a new held-out period and profiling are optional future experiments, not completed features.

The old PC-hosted temporary tunnel is historical and was unavailable in the audit. Use the permanent Pages URL from the README. Recorded test counts and timings retain their original revisions and workloads. [Ownership exercises](OWNERSHIP.md) are unfinished until actually completed by the owner.

Code uses [MIT](../LICENSE); the unchanged dataset-rights explanation is in [NOTICE](../NOTICE.md). No new license for external data is granted.
