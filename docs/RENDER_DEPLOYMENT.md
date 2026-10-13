# GitHub → Docker → public Render demonstration

## Current status

The cloud configuration and entrypoint are prepared. Local-process checks pass for the reverse
proxy, API, Streamlit, authentication, feedback retries, WebSocket upgrades, health command, and
graceful shutdown. Docker execution, GitHub publication, GHCR publication, and the public Render
service have not run because the required account connections are absent.

## Repository and CI

Publish the source to your GitHub account using the existing publishing script, or connect
GitHub so the repository can be created and pushed on your behalf. Generated datasets,
credentials, and real-data bundles are excluded. The synthetic model is built during the image
build rather than committed as training data.

The `checks` workflow runs Python checks plus two Docker startup paths: separate-service
Compose and the single-port cloud image. The `container-image` workflow validates Python,
builds the cloud image, checks API/UI readiness, and only then publishes it to GHCR.

## Create the public demonstration

Connect Render and grant it access to the GitHub repository. Create a Blueprint from that
repository with its root `render.yaml` file. The specification selects:

- Docker runtime using the default `cloud` target.
- A free web-service plan in Singapore.
- One exposed port, taken from `PORT` (default 10000).
- `/api/ready` as the readiness check.
- A generated `ATLAS_API_KEY` shared by the internal API and Streamlit process.
- Automatic updates after linked-branch CI checks pass.
- An explicit temporary-feedback notice in the UI.

The free configuration does not attach a persistent disk. Imported research data are not
downloaded on startup; the hosted catalog and example users are synthetic. Render terminates
public TLS; Caddy only routes internal HTTP traffic. The external URL comes from the successful
Render service creation, not from an invented hostname.

Official references: https://render.com/docs/docker,
https://render.com/docs/blueprint-spec, https://render.com/docs/free.

## Verify before adding the live URL to your résumé

Use the actual returned URL:

```bash
export ATLAS_PUBLIC_URL="https://YOUR-ACTUAL-SERVICE.onrender.com"
curl --fail "$ATLAS_PUBLIC_URL/api/ready"
curl --fail "$ATLAS_PUBLIC_URL/_stcore/health"
```

Visit the root page and verify a new-user preference flow and feedback submission. The API
accepts direct authenticated requests with your generated key; keep that key in provider/repo
secrets rather than screenshots, README files, or public URLs.

Check Render's deploy logs and resource metrics. A locally successful benchmark does not
establish cloud latency under the free plan's resource limits. A service may sleep when idle;
measure cold starts separately. Feedback on the free service resets after restart/redeploy.

## Résumé evidence to retain

After remote checks actually succeed, retain:

1. The real GitHub repository URL.
2. A passed Docker CI run URL.
3. The actual GHCR image tag/digest if publication was run.
4. The real live demo URL.
5. The recorded local benchmark and its workload description.
6. One failure analysis and one experiment you personally reproduced.

Until those external steps succeed, describe the project as implemented and locally verified,
with deployment configuration prepared. After successful hosting, a factual deployment bullet
can say:

“Containerized and deployed a recommendation demo with FastAPI, FAISS, and LightGBM; added
GitHub Actions checks, model-bundle validation, feedback provenance, and rollback verification.”

Do not attach the local 56 ms p95 measurement to the hosted service unless you run and record
the same benchmark against that actual public deployment.
