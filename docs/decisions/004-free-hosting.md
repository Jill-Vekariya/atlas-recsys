# Decision 004: share the real Docker application without billing

## Constraint

The owner requires no hosting payment and no card entry. The demonstration should exercise
the actual recommendation application and its model artifacts.

## Evidence

The Docker build, application checks, and GitHub Actions checks passed. The image is available
anonymously from GHCR. Render CLI authorization succeeded, but both image-backed and Git-backed
creation with the free plan returned HTTP 402 requiring payment information. No service was
created there.

## Decision

Keep the trained application on the configured PC and share its single serving port with a
Cloudflare Quick Tunnel. Keep the permanent repository, image digest, experiment reports, and
CI evidence on GitHub. The direct API remains authenticated; the Streamlit server handles API
authentication internally. Public verification does not transmit an API key through the tunnel.

## Consequence

The public demonstration depends on the PC remaining online, and the hostname changes after
a tunnel restart. This is a working interview demonstration with a clear operating limitation.
It does not establish managed-cloud availability or production scale. The repository and Docker
image remain usable even when the temporary demonstration is offline.
