# Verification record

Recorded on 14 October 2026 using Python 3.12.14 on a CPU host.

| Check | Status | Evidence |
|---|---|---|
| Clean dependency installation | Passed | `uv sync --frozen --extra dev` completed |
| Unit/integration tests | Passed | 24 tests; temporal history, cold withholding, loss, export parity, API, feedback, concurrency, routing, serving-import isolation |
| Ruff lint and formatting | Passed | Source, scripts, and tests checked |
| Synthetic end-to-end training | Passed | `reports/synthetic/*.json` |
| Amazon data preparation/training/evaluation | Passed | `reports/amazon/*.json` |
| MovieLens preparation/training/evaluation | Passed | `reports/movielens/*.json` |
| MovieLens item representation ablations | Passed | Validation reports under `reports/movielens/content_only` and `identity_only` |
| Real HTTP load test | Passed locally | 500 measured requests per workload; JSON reports |
| Streamlit existing/new-user/feedback flows | Passed | `reports/synthetic/ui_verification.json` |
| Canary failure detection and rollback | Passed locally | `reports/synthetic/canary.json` |
| YAML parsing and shell syntax | Passed | Compose/workflow/prometheus YAML parsed; publishing shell syntax checked |
| Cloud entrypoint/reverse proxy | Passed as local processes | `reports/synthetic/cloud_startup.json`; API/UI, auth, feedback, WebSocket, health, graceful shutdown |
| Docker build/start | Not run | Docker daemon unavailable; GH CI contains startup checks |
| GitHub publication and Actions | Not run | GitHub plugin found but not connected |
| GHCR publication | Not run | Workflow prepared; no authenticated publish |
| Public VM/domain/TLS hosting | Not run | Deployment files prepared; no hosting target supplied |
| Render public deployment | Not run | Blueprint supplied; Render and GitHub accounts unconnected |
| Real-user A/B quality lift | Not measured | No real experiment participants or business outcome data |

The current Starlette version emits a TestClient/httpx deprecation warning. Tests pass, and
runtime HTTP serving was independently exercised. Pinning is recorded in the lockfile; revisit
the TestClient adapter when upgrading those packages.

The repository does not claim every advanced model beats the baseline. See RESULTS.md for
the failed ranker comparison and small cold-cohort benefit.
