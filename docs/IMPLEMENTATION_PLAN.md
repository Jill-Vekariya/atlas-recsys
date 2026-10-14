# Atlas implementation plan (14 October 2026)

## Scope and evidence

This is an incremental improvement plan for the existing repository, not a rebuild. Reviewed: README.md, pyproject.toml, docs/RESULTS.md, docs/VERIFICATION.md, tests/ listing, repository structure and current Git status. HEAD at audit: `6731662`; working tree was clean before this document. Statements below distinguish recorded evidence from checks run in this session.

## Architecture summary

Offline: dataset preparation -> chronological train/ranker/validation/test windows -> popularity, ALS, content and two-tower candidates -> FAISS retrieval -> LightGBM ranking -> metric/report generation. Online: versioned model bundle -> FastAPI serving and feedback logging -> Streamlit and browser demonstration. Documentation records canary routing, metrics, and rollback. Architecture behavior requires re-verification against code and tests before modifications.

## Feature status (evidence-limited)

| Feature | Status | Evidence / next check |
| --- | --- | --- |
| Published browser demonstration | IMPLEMENTED_BUT_INSUFFICIENTLY_TESTED | README and prior verification notes; not tested in this session |
| Amazon/MovieLens benchmark reports | IMPLEMENTED_BUT_INSUFFICIENTLY_TESTED | docs/RESULTS.md includes real-data metrics; rerun provenance and report generation |
| Baselines, retriever and ranker | IMPLEMENTED_BUT_INSUFFICIENTLY_TESTED | README, results, and prior CI record; inspect code and rerun unit/integration tests |
| Versioned serving, canary and rollback | IMPLEMENTED_BUT_INSUFFICIENTLY_TESTED | docs/VERIFICATION.md records past checks; validate on current environment |
| Local developer verification | BLOCKED_BY_ENVIRONMENT | PowerShell `uv` not found; default Python 3.12 has no pytest or uv |
| Implementation plan | IMPLEMENTED_BUT_INSUFFICIENTLY_TESTED | This document is the first audit pass, to expand after full source review |

## Highest-priority verified opportunities

1. **Restore local verification.** Current PowerShell does not resolve `uv`; default Python 3.12 lacks pytest. Confirm intended virtual environment or install tooling without changing pinned dependencies. Run `uv sync --frozen --extra dev`, `uv run pytest -q`, `uv run ruff check src tests scripts`, and `uv run ruff format --check src tests scripts`.
2. **Investigate the ranking regression.** MovieLens test NDCG@10: popularity 0.2598, tower 0.2340, ranked 0.2321, ALS 0.2468. Recorded paired ranked-minus-ALS interval is negative. Investigate candidate recall, labels, ranker features, cohort behavior, and capacity; preserve test isolation.
3. **Investigate Amazon data sparsity.** Recorded Amazon evaluation has only two returning users with positive pre-cutoff history and 27 personalized retriever examples. Do not interpret tied model results as evidence of equivalent model quality; assess a richer workload/configuration without selecting on test.
4. **Make model quality versus cold-start trade-offs explicit.** MovieLens cold Recall@100: content 0.0064, tower 0.0164, ranked 0.0111; overall quality differs. Produce validation-first cohort breakdowns with uncertainty and documented catalog assumptions.
5. **Revalidate serving cost and rollback on the current machine.** Recorded tests are historical, including previous Docker and HTTP checks; run local workload only after a functional install, and do not assert production SLA compliance.

## Incremental phases and acceptance criteria

### Phase A — developer environment and repeatable verification
- Identify Python/uv environment and restore reproducible installation.
- Pass or diagnose tests, lint and formatting; record exact commands, versions and failures.
- Acceptance: machine-readable outputs or clearly documented blockers; no hidden failing checks.

### Phase B — leakage and evaluation audit
- Inspect time splits, training-feature cutoffs, negative sampling, controlled item withholding, candidate generation and metric denominators.
- Add focused tests for any confirmed edge cases without altering existing test definitions to hide failures.
- Acceptance: traceable evaluation population, cutoff invariants and evidence for each corrected defect.

### Phase C — ranking and cold-start investigation
- Diagnose the recorded MovieLens ranking regression using validation, never tuning to final test.
- Compare content-only, identity-only, hybrid and baseline models across relevant cohorts and seeds where feasible.
- Acceptance: reports generated from actual runs with run IDs, uncertainty, costs and negative findings preserved.

### Phase D — latency, reliability and portfolio evidence
- Recheck HTTP latency/queueing at specified load, model bundle compatibility, feedback idempotency, canary and rollback; document hardware and workload.
- Refresh RESULTS, MODEL_CARD, INTERVIEW_GUIDE, and README only after measured verification.
- Acceptance: reproducible commands and artifacts for every claimed result.

## Risks and safeguards

- Historical metadata is not necessarily point-in-time correct; label transductive assumptions.
- Review/rating data do not provide complete impressions or negative preferences; avoid CTR or business-impact claims.
- Single-seed and small-cohort estimates are uncertain; do not imply statistically established uplift.
- Existing bundles and published deployment are retained; no destructive Git actions, bundle overwrites or public deploys without authorization.

## First-session verification

On 14 October 2026 the repository was located at `C:\Users\jillv\Documents\Atlas-Recsys\atlas`; initial Git status was clean. Python reported 3.12.10. Commands `uv run pytest -q`, `python -m uv --version`, and `python -m pytest --version` could not run because tools/modules were unavailable in the default shell. Prior 26-test CI success was read from docs/VERIFICATION.md, not reproduced in this session.

**Next action:** locate/install the intended uv environment, run checks, then expand this audit with source-level confirmation before architectural edits.
