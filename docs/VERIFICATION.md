# Verification record

Python experiments used Python 3.12.14 on a CPU host. Remote Docker and GitHub checks were
recorded on 13 October 2026; Docker used CPython 3.12.15 in Linux containers.

| Check | Status | Evidence |
|---|---|---|
| Clean dependency installation | Passed | `uv sync --frozen --extra dev` completed |
| Unit/integration tests | Passed | 26 tests in GitHub Actions, including ALS no-signal cold onboarding; temporal history, cold withholding, loss, export parity, API, feedback, concurrency, routing, serving-import isolation, public-check credential isolation; [CI evidence](https://github.com/Jill-Vekariya/atlas-recsys/actions/runs/38468949550) |
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

The primary public demonstration is the GitHub Pages browser lab and does not depend on the PC.
The optional full Docker tunnel depends on the PC, Docker, application, and tunnel remaining online. No managed-cloud availability
or public workload latency is claimed. No hosting payment or card entry was performed.

## Browser deployment (13–14 October 2026)

- GitHub Pages deployment [38474619205](https://github.com/Jill-Vekariya/atlas-recsys/actions/runs/38474619205) passed.
- Five model/protocol tests compare 16 Python reference profiles across 300 items (4,800 candidate calculations).
- Four Chrome/Chromium UI tests cover all modes, cold onboarding, feedback persistence, filters, evidence, and mobile layout.
- Exported LightGBM predictions match the saved Python reference; floating-point vector comparisons use explicit tolerances.
- The initial backend commit failed CI formatting on one line. The correction passed [Python/Docker CI 38520865560](https://github.com/Jill-Vekariya/atlas-recsys/actions/runs/38520865560).
- The demo uses synthetic profiles; evidence reports separately retain real Amazon/MovieLens evaluation.

The corrected Pages deployment [38520865593](https://github.com/Jill-Vekariya/atlas-recsys/actions/runs/38520865593) passed all numerical and browser gates.
The image publication [38521025493](https://github.com/Jill-Vekariya/atlas-recsys/actions/runs/38521025493) passed tests and a live container smoke check before pushing.
An independent browser confirmed the deployed lab's profile selection, cold onboarding/content fallback,
feedback exclusion, ranking/held-out filtering, evidence, and provenance.
The Windows deployed-site Playwright attempt encountered `ERR_NETWORK_ACCESS_DENIED`; this is not
recorded as a passing test. Local Windows UI tests and hosted GitHub Chromium tests passed.

## Configured PC update (14 October 2026)

The PC now runs the corrected serving code in `atlas-recsys:serving-fix`. Slow registry downloads
and a failed package download prevented a fresh full local build. The installed image reuses
the existing dependency image and replaces the two changed serving modules from the CI-tested
source. It is a separately identified local image, not the GHCR publication digest.

The replacement passed authenticated local API/UI/docs/feedback/metrics/WebSocket checks and
a live ALS cold-onboarding regression. Reports: `reports/deployment/docker-update.json` and
`docker-cold-onboarding.json`. The named feedback volume was retained. The previous container
is stopped as `atlas-recsys-demo-before-20261014` for rollback. The public GHCR image separately
passed GitHub build/smoke/publication checks and is pinned in `image-manifest.json`.
