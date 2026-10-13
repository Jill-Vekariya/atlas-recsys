# Local containers, GitHub, and external hosting

## What has and has not run

The Python environment, model experiments, HTTP benchmark, and UI flows were exercised. Docker
build/start and authenticated application checks passed on the configured PC. GitHub Actions
passed Python and Docker checks, and GHCR publication was verified with anonymous image access.
The full application is publicly shared from that PC over a free Cloudflare Quick Tunnel.
See [FREE_DEMO.md](FREE_DEMO.md) for the active no-card setup, its temporary URL, and operating
limits. Managed Render creation was blocked by its account requirement and was not used.

## Local Docker

```bash
docker compose config
docker compose up --build -d
docker compose logs bootstrap api demo
curl --fail http://127.0.0.1:8000/ready
curl --fail http://127.0.0.1:8501/_stcore/health
```

Use `docker compose stop` to retain data. `docker compose down` retains named volumes.
`docker compose down -v` deliberately deletes generated bundles and feedback; use it only
for a fresh demonstration. The non-root process stores state in named volumes.

The bootstrap script is idempotent and uses synthetic data. It does not download research data
on a public server. The image dependency source routes PyTorch to CPU wheels; all direct and
transitive Python versions are recorded in `uv.lock`. Base container tags are not digest-pinned.

## Publish to your GitHub account

The current repository is already public at https://github.com/Jill-Vekariya/atlas-recsys.
For a new fork, install GitHub CLI, authenticate it, and configure your actual Git author identity.

```bash
gh auth login
git config --global user.name "YOUR NAME"
git config --global user.email "YOUR GITHUB EMAIL"
ATLAS_VISIBILITY=public bash scripts/publish_github.sh
```

The script defaults to a private repository unless you explicitly choose public visibility.
It stops when an origin already exists rather than pushing to an unknown remote. Review the
staged files before publishing if you have added your own data or credentials.

The Python CI job checks formatting, meaningful tests, and the synthetic pipeline. The Docker
job checks Compose initialization and API/demo readiness. The current repository passed
[these checks](https://github.com/Jill-Vekariya/atlas-recsys/actions/runs/38468949550).

Publish a container through the `container-image` workflow after CI passes:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The workflow publishes to GHCR using the repository-scoped token. Inspect workflow logs and
the resulting image before deploying. Build/signing provenance is requested; it is not a
claim that an external security audit has occurred.

## Public demonstration on a VM

Use a Linux VM with Docker Compose and enough RAM for CPU PyTorch, the model bundle, API,
and Streamlit. Start with 4 GB RAM for the small synthetic demo and measure actual resource
usage. No hosting price or provisioning is implied by this recommendation.

1. Point a domain's DNS A/AAAA records to the VM.
2. Permit inbound ports 80 and 443. Keep API port 8000 private.
3. Copy or clone the repository.
4. Set the required environment values on the VM.
5. Validate and start the standalone production Compose file.

```bash
export ATLAS_DOMAIN="atlas.your-domain.example"
export ATLAS_API_KEY="A-LONG-RANDOM-SECRET-YOU-GENERATE"
docker compose -f deploy/compose.production.yaml config
docker compose -f deploy/compose.production.yaml up --build -d
```

Replace the example domain and secret. Configure environment files on the VM rather than
committing secrets. Caddy obtains and renews TLS certificates when domain and network access
are valid. Streamlit calls the API over the private Compose network with a server-side API key.

After deployment, verify:

```bash
curl --fail "https://$ATLAS_DOMAIN/api/ready"
curl --fail -H "X-API-Key: $ATLAS_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"new-demo-user","source":"demo"}' \
  "https://$ATLAS_DOMAIN/api/recommend"
```

Visit `https://YOUR_DOMAIN/` for the demo and `/api/docs` for API documentation.
The demo is anonymous and uses synthetic data. Application-user authentication, multi-tenant
permissions, and per-account quotas are not implemented.

## Operating the container

```bash
docker compose exec api atlas inspect --bundle artifacts/synthetic-v1
docker compose exec api atlas export-feedback --output data/feedback/export.jsonl
docker compose exec api atlas rollback
```

The API container mounts artifacts but does not mount the data volume in the local composition.
An export written inside that container is temporary unless copied out with `docker compose cp`
or directed into the artifacts volume. Back up the artifact volume and SQLite database before
updates. Use SQLite's backup API for a consistent live backup instead of copying only its main
file while WAL writes are active.

The current router is one-host state, with one operator writing routing changes. Multiple hosts
would need shared version publication, staged readiness checks, and a coordinated promotion
mechanism. Native retrieval deadlines are detected after execution rather than preempted.
