# Atlas final engineering verification — 14 October 2026

This note separates measured historical runs from new diagnostics. The latest measurements
were produced on a Windows 12-logical-CPU host with Python 3.12.10, using the **synthetic**
300-item bundle. They are not MovieLens production workload numbers.

## Throughput diagnosis

| Controlled run | Target | Requests | Achieved RPS | p95 end-to-end | p95 dispatch lag | p95 client in-flight | p95 server processing | HTTP errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Newly instrumented low load | 5 RPS for 5 s | 25 | 5.15 | 56.90 ms | 10.51 ms | 52.28 ms | 32.70 ms | 0% |
| Newly instrumented high load | 50 RPS for 10 s | 500 | 19.13 | 15697.89 ms | 14128.20 ms | 3896.71 ms | 1009.54 ms | 0% |
| Prior high-load run (before instrumentation) | 50 RPS for 10 s | 500 | 19.51 | 15183.76 ms | 13545.08 ms | not recorded | not recorded | 0% |

Reports: `reports/verification-20261014-7a2592b/http_load_diagnostic_5rps.json`,
`http_load_diagnostic_50rps.json`, and `http_load_after_sqlite_fix.json`.

The scheduled-arrival latency includes asynchronous scheduler wakeup, semaphore waiting, and
client HTTP elapsed time. p95 components are separate marginal quantiles and must not be
added together. The client-in-flight time includes network and queueing as well as server
processing; server processing is the API's own response field. The high-load run overran its
requested duration by 16.14 seconds, so achieved throughput was far below the requested
arrival rate. This is evidence of substantial overload/contention under this local
configuration; the exact attribution between host contention, Python scheduling, worker
concurrency, SQLite writes, and model compute is **not yet isolated**.

**Status:** At 5 RPS the synthetic workload meets 150 ms p95. At 50 RPS it does
**not**. No claim of sustained 50 RPS / 150 ms is warranted on this PC. The
historical MovieLens 55.95 ms p95 is a different recorded host/workload and
does not override this result.

## Reproduction

```powershell
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
uv run atlas verify-local --rate 5 --duration 5 --output reports/new-low-load.json
uv run atlas verify-local --rate 50 --duration 10 --output reports/new-high-load.json
uv run python scripts/cohort_evidence.py --report reports/movielens/validation.json
uv run python scripts/cohort_evidence.py --report reports/movielens/test.json
uv run python scripts/model_selection_audit.py --report-dir reports/movielens
uv run pytest -q
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
```

Choose new output paths; do not overwrite historical reports. Run load tests without
parallel browser tests and record CPU pressure, server process count, SQLite volume
location, and background workload. The benchmark has added separate wakeup/semaphore
instrumentation and client/server time fields without changing the serving model.

## Cohort evidence — recorded real-data results, NOT fresh training

- MovieLens validation: 71 eligible evaluated users; 14 returning with positive
  pre-cutoff history, 57 new/zero-positive-history.
- MovieLens test: 96 evaluated users, 30 returning and 66 new/zero-positive-history
  (as recorded in `test.json`).
- The validation-selected tower underperformed the popularity baseline on final-test
  NDCG@10: 0.233961 versus 0.259801, absolute difference -0.025840.
- The recorded controlled-cold Recall@100 was approximately 0.016431 for tower
  and 0 for popularity, a narrow retrieval result, not general model superiority.
- Amazon has only 2 returning test users, rendering personalized conclusions weak.

`scripts/cohort_evidence.py` reports the already recorded aggregate cohort
metrics, cohort sizes, and existing paired intervals. It does not derive new
bootstrap intervals from aggregate means: new pairwise confidence intervals
need per-user paired outcomes. No second seed, new test data, or new model was
trained.

## SQLite and release consistency

The existing local `src/atlas/storage.py` correction explicitly closes each
SQLite connection after a transaction and eliminated a previous Windows cleanup
exception in the local verifier. This was tested but was uncommitted when the
verification work began. Preserve original model bundles and feedback data.

## Interview / resume claims

**Supported:** implemented and tested multi-baseline retriever/ranker, controlled
temporal evaluation, checksum-validated bundles, synthetic browser lab, FastAPI
serving, feedback idempotency, fault-injected canary rollback, and historical
real-data results.

**Not supported:** production SLA, a consistent 50 RPS local target, online CTR or
revenue uplift, superior overall two-tower test performance, or statistically
established cold-start generalization across multiple seeds.

Before a recruiter interview, explain why validation selected the tower while
the held-out test favored popularity, why new-user fallback dilutes overall
comparisons, and why 50 RPS / 150 ms cannot currently be claimed.
