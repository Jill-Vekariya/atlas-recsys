# Verification record

Python experiments used Python 3.12.14 on a CPU host. Remote Docker and GitHub checks were
recorded on 13 October 2026; Docker used CPython 3.12.15 in Linux containers.

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
| Docker build/start | Passed | Docker Desktop 29.8.2; cloud image healthy; `reports/synthetic/docker_startup.json` |
| Docker API/UI/auth/feedback/WebSocket smoke checks | Passed | `scripts/verify_deployment.py` and Docker startup report |
| Feedback persistence across container replacement | Passed | Dedicated named volume; recorded in Docker startup report |
| GitHub publication and Actions | Passed | [Public repository](https://github.com/Jill-Vekariya/atlas-recsys); [Python and Docker checks](https://github.com/Jill-Vekariya/atlas-recsys/actions/runs/38465119077) |
| GHCR publication | Passed | [Release workflow](https://github.com/Jill-Vekariya/atlas-recsys/actions/runs/38465120714); digest in `reports/deployment/image-manifest.json` |
| Anonymous published-image access | Passed | Registry manifest returned HTTP 200 with the expected digest; `reports/deployment/registry_access.json` |
| No-card public Docker demonstration | Passed | `reports/public_demo/deployment.json`; configured PC shared through Cloudflare Quick Tunnel |
| Public UI/API readiness and WebSocket checks | Passed without credentials | `scripts/verify_public_endpoint.py`; direct unauthenticated API requests rejected |
| Public VM/domain/TLS hosting | Not run | Deployment files prepared; no hosting target supplied |
| Render public deployment | Blocked by account requirement | CLI authorization succeeded; both image-backed and Git-backed free-plan creation returned HTTP 402 requiring payment information. No service created; `reports/render/deployment_attempt.json` |
| Real-user A/B quality lift | Not measured | No real experiment participants or business outcome data |

The current Starlette version emits a TestClient/httpx deprecation warning. Tests pass, and
runtime HTTP serving was independently exercised. Pinning is recorded in the lockfile; revisit
the TestClient adapter when upgrading those packages.

The repository does not claim every advanced model beats the baseline. See RESULTS.md for
the failed ranker comparison and small cold-cohort benefit.

The public demonstration is self-hosted on the configured PC through a temporary tunnel. It
depends on the PC, Docker, application, and tunnel remaining online. No managed-cloud availability
or public workload latency is claimed. No hosting payment or card entry was performed.
