## Why

The current `frontend/Dockerfile` packages the entire application into one image, which is useful for the initial hosting environment but couples the React frontend and FastAPI backend for Kubernetes. The cluster can now run worker workloads, so we need independently deployable images while preserving the unified image as a compatibility path.

## What Changes

- Rename the current unified image definition to `frontend/Dockerfile.unified` without changing its runtime behavior.
- Add `frontend/Dockerfile` for a production frontend-only image that builds the Vite application and serves its static assets.
- Add a repository-root `Dockerfile` for a backend-only image that runs the existing FastAPI API.
- Keep frontend `/api` requests same-origin compatible for a later Kubernetes routing layer.
- Add documented build, run, health-check, and registry-tagging commands for all image variants.
- Verify that the unified image remains buildable and runnable after the Dockerfile rename.

## Capabilities

### New Capabilities

- `service-images`: Independently buildable and runnable frontend-only and backend-only container images for split deployments.

### Modified Capabilities

None. The existing `single-container-runtime` capability remains supported by `frontend/Dockerfile.unified`.

## Impact

- Docker build definitions and image documentation at the repository root and under `frontend/`.
- Backend runtime entrypoint remains the existing FastAPI API app; no API route or graph contract changes are intended.
- Frontend production serving changes from the unified Python static server to a static web server image, with Kubernetes routing handled by a later deployment change.
- CI or local verification must build three image variants and check their health/serving behavior.
