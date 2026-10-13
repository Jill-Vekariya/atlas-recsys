# Configured PC demonstration

Atlas is installed under `Documents/Atlas-Recsys/atlas` on the configured Windows PC. Docker
Desktop runs the `atlas-recsys-demo` container, exposing the lab at http://localhost:10080 and
API documentation at http://localhost:10080/api/docs. These URLs work on that PC.

The container uses `--restart unless-stopped`; Docker Desktop must be running. A dedicated
`atlas-recsys-demo-data` volume preserves its model registry and synthetic-demo feedback.
Feedback survived replacing the container with the final image. API authentication is enabled,
and the dashboard uses the configured key internally.

Use PowerShell to manage this demonstration:

```powershell
docker ps --filter name=atlas-recsys-demo
docker logs --tail 50 atlas-recsys-demo
docker stop atlas-recsys-demo
docker start atlas-recsys-demo
```

To rerun the application checks inside the running container:

```powershell
docker exec atlas-recsys-demo python scripts/verify_deployment.py
```

The verifier labels its feedback as demo traffic. It checks API/UI readiness, API authentication,
new-user fallback, feedback retries, metrics, Swagger routing, and the dashboard WebSocket.
It does not measure recommendation quality or cloud load capacity.

Public sharing is configured through Cloudflare Quick Tunnel; see FREE_DEMO.md. The public URL
depends on this PC and Docker staying online. Feedback persists in the local dedicated volume.
