# Free demonstration without a card

The configured Windows PC runs the complete Docker application. A Cloudflare Quick Tunnel
shares it over HTTPS without a Cloudflare account, a purchased domain, or card details.
This preserves the actual FastAPI, FAISS, LightGBM, Streamlit, and model-bundle implementation.

The current public URL is recorded in `reports/public_demo/deployment.json`. It is temporary:
the PC, Docker Desktop, the application container, and the tunnel must stay running. Restarting
the tunnel creates a new hostname. Use the permanent GitHub repository link on a resume, and
open the demonstration before an interview.

The configured containers are `atlas-recsys-demo` and `atlas-recsys-public-tunnel`. They communicate
on the dedicated `atlas-recsys-demo-network` Docker network. The tunnel exposes only the Atlas
application; local application ports stay bound to loopback.

Check or stop the public demonstration from PowerShell:

```powershell
docker ps --filter name=atlas-recsys
docker logs --tail 80 atlas-recsys-public-tunnel
docker stop atlas-recsys-public-tunnel
```

To resume it, start the application first and then the tunnel. Read the new URL from its logs:

```powershell
docker start atlas-recsys-demo
docker start atlas-recsys-public-tunnel
docker logs --tail 80 atlas-recsys-public-tunnel
```

Update the recorded public link after a tunnel restart; an old URL must not be described as live.
Both containers have a restart policy, but a fresh tunnel process still creates a fresh hostname.

Public checks use `scripts/verify_public_endpoint.py`. It never reads or transmits an API key.
It checks public readiness, frontend HTML, Swagger routing, authentication rejection, and the
dashboard WebSocket. Authenticated recommendation, feedback, monitoring, and persistence checks
were separately completed inside the local Docker application. The dashboard's server calls
its internal API using the key locally; the key is not exposed to visitors.

Render was not used because authenticated free-plan creation requested payment information.
No paid service, trial subscription, card entry, or hosting upgrade was performed.

Quick Tunnels have no uptime guarantee, cap concurrent in-flight requests at 200, and do not
support Server-Sent Events. The demonstration uses WebSockets. These are testing constraints,
not production availability guarantees. Official reference:
https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/.
