# Serving, feedback, and rollback runbook

## Daily checks

- `/health` checks process liveness; `/ready` validates loaded routing state.
- Inspect request/error/fallback counters and retrieval/ranking latency histograms.
- Distinguish expected new-user fallback from retrieval-failure fallback.
- Confirm the active model/index/feature bundle version.
- Inspect missing onboarding-category counts separately from recommendation quality.

`/metrics` requires the configured API key. `deploy/prometheus.yml` supplies a local scrape
template; configure its key header if needed. Histograms report processing latency, whereas
the HTTP benchmark reports planned arrival through response completion, including queueing.

## A model release

1. Prepare a new config with a fresh bundle/report directory.
2. Train/evaluate on documented chronological windows.
3. Inspect baseline comparisons, cohort sizes, confidence intervals, and metadata assumptions.
4. Validate the bundle with `atlas inspect` and run API compatibility checks.
5. Start a small canary with `atlas activate --bundle NEW_BUNDLE --canary-percent 5`.
6. Compare service latency, errors, and unexpected fallback rates with primary traffic.
7. Promote only after a documented guard window. Delayed quality labels may require a longer wait.

This implementation supports routing, logging, promotion, and rollback. The demonstration
automates a specific injected-failure guard; it is not a permanently running production rollout
controller. Do not infer recommendation uplift from service-health metrics.

## Rollback

```bash
uv run atlas rollback --state artifacts/registry.json
```

With a candidate present, rollback removes canary traffic and leaves primary unchanged. After
a full activation, rollback restores the previous validated primary. The serving process reads
atomic routing changes on its next request. In-flight requests finish using their captured
bundle; this maintains model/index consistency.

## Reproduce the failure demonstration

```bash
uv run atlas canary-demo --config configs/smoke.yaml
```

The isolated sandbox creates a candidate clone, assigns 25% of synthetic users deterministically,
injects a 25 ms delay and retrieval exception only into canary requests, compares 20 requests
per route, and rolls back when its retrieval-failure rate exceeds primary by 0.2. The report
records observations and post-rollback routing. It does not mutate the live registry.

## Feedback

Use stable event IDs when retrying the same feedback. The store uses a SQLite immediate
transaction to serialize competing retries. Identical retries return `duplicate`; conflicting
payloads under the same event ID return 409. Feedback referring to unexposed items is rejected.

Export into a staging file, preserve its source, and apply a separate label policy before a new
training cycle. Feedback does not immediately change a user's recommendations in this version.

## Recovery cases

| Failure | Behavior | Operator action |
|---|---|---|
| New user without preferences | Popularity fallback | Offer preference onboarding |
| Unknown preference category | Counted; available preferences still apply | Check taxonomy/version |
| Retrieval exception | Popularity fallback and error metric | Inspect logs, validate index, roll back |
| Slow retrieval result | Post-execution deadline fallback | Benchmark candidate/index settings |
| Corrupted bundle asset | Activation fails before changing routing | Rebuild or restore trusted bundle |
| Missing or invalid routing file | Readiness/requests fail | Restore a valid atomic state file |
| SQLite unavailable/full | Exposure or feedback write fails | Restore storage and inspect capacity |

SQLite write failures are surfaced; the system does not silently claim an exposure was recorded.
There is no automatic recovery from disk failure or multi-node failover.
