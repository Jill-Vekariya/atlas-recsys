# Portfolio evidence record

This table preserves historical execution evidence. For the supported demonstration, current limitations and new verification, start with [current status](CURRENT_STATUS.md). Historical test counts and host-specific timings are not current-head guarantees.

| Evidence | Status | Location |
|---|---|---|
| Source implementation | Complete | Repository source and scripts |
| Python verification | Passed in GitHub Actions | 26 tests plus lint/format; Python/Docker CI `38520865560` |
| Real-data evaluation | Recorded | Amazon and MovieLens JSON reports |
| Local HTTP benchmark | Recorded | `reports/movielens/http_load.json` |
| Cloud entrypoint application check | Passed locally | `reports/synthetic/cloud_startup.json` |
| Local Docker deployment | Passed | `reports/synthetic/docker_startup.json`; PC demo at http://localhost:10080 |
| Public GitHub repository | Published | https://github.com/Jill-Vekariya/atlas-recsys |
| Docker CI run | Passed | https://github.com/Jill-Vekariya/atlas-recsys/actions/runs/38520865560 |
| Published Docker image | Published and anonymously accessible | `ghcr.io/jill-vekariya/atlas-recsys:latest`; digest in `reports/deployment/image-manifest.json` |
| Permanent browser lab | Deployed with model/UI gates | https://jill-vekariya.github.io/atlas-recsys/ |
| Live Render demo | Blocked by Render account requirement | Authenticated free-plan creation returned HTTP 402; no public URL yet |
| Historical no-card Docker demonstration | Previously verified; unavailable in the 2026-10-23 audit (HTTP 503) | Original address and observations remain in `reports/public_demo/deployment.json`. Use the permanent browser lab above for sharing. |

Fill external URLs only from successful platform responses. The locally tested system and
prepared Docker configuration can be described now; “deployed” requires the corresponding
service to be running and verified.

Current evidence supports:

“Built and containerized an end-to-end recommendation platform using PyTorch, FAISS, LightGBM,
and FastAPI; evaluated chronological Amazon/MovieLens workloads and added GitHub Actions tests,
authenticated serving, idempotent feedback, monitoring, and verified rollback.”

The recorded MovieLens load test measured 500 requests at about 50 requests/second with roughly
56 ms p95 on a local CPU host. Identify that workload if using the number; it is not hosted latency.
The permanent GitHub Pages demo runs the exported trained models in-browser. Link it alongside
the GitHub repository; describe the optional full Docker tunnel as temporary PC hosting. Personal ownership exercises remain yours
to complete so you can explain the evaluation, failed model comparisons, and operational choices.
