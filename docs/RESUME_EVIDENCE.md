# Portfolio evidence record

| Evidence | Status | Location |
|---|---|---|
| Source implementation | Complete | Repository source and scripts |
| Python verification | Passed locally | 24 tests plus lint/format checks |
| Real-data evaluation | Recorded | Amazon and MovieLens JSON reports |
| Local HTTP benchmark | Recorded | `reports/movielens/http_load.json` |
| Cloud entrypoint application check | Passed locally | `reports/synthetic/cloud_startup.json` |
| Local Docker deployment | Passed | `reports/synthetic/docker_startup.json`; PC demo at http://localhost:10080 |
| Public GitHub repository | Published | https://github.com/Jill-Vekariya/atlas-recsys |
| Docker CI run | Passed | https://github.com/Jill-Vekariya/atlas-recsys/actions/runs/38465119077 |
| Published Docker image | Published and anonymously accessible | `ghcr.io/jill-vekariya/atlas-recsys:latest`; digest in `reports/deployment/image-manifest.json` |
| Live Render demo | Blocked by Render account requirement | Authenticated free-plan creation returned HTTP 402; no public URL yet |
| Public no-card Docker demonstration | Verified | https://cotton-gender-pts-metric.trycloudflare.com; temporary PC-hosted link, report in `reports/public_demo/deployment.json` |

Fill external URLs only from successful platform responses. The locally tested system and
prepared Docker configuration can be described now; “deployed” requires the corresponding
service to be running and verified.

Current evidence supports:

“Built and containerized an end-to-end recommendation platform using PyTorch, FAISS, LightGBM,
and FastAPI; evaluated chronological Amazon/MovieLens workloads and added GitHub Actions tests,
authenticated serving, idempotent feedback, monitoring, and verified rollback.”

The recorded MovieLens load test measured 500 requests at about 50 requests/second with roughly
56 ms p95 on a local CPU host. Identify that workload if using the number; it is not hosted latency.
The public demonstration is verified; label it as PC-hosted through a temporary tunnel. Use the
permanent GitHub repository as the primary resume link. Personal ownership exercises remain yours
to complete so you can explain the evaluation, failed model comparisons, and operational choices.
