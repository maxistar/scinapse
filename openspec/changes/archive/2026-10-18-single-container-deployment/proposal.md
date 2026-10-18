## Why

The hosting environment accepts only one deployable container image, while the application currently requires a separate static frontend container and FastAPI backend process. The frontend and API need to be packaged behind one public port so live research searches work in that hosting environment.

## What Changes

- Build the React frontend and Python backend into one production image.
- Serve the compiled frontend and existing `/api` endpoints from the same application and public port.
- Preserve the current local development workflow with Vite proxying `/api` to the backend.
- Keep secrets supplied through runtime environment variables rather than baking `.env` into the image.
- Add container health and deployment instructions for the unified image.
- Keep the single-process runtime compatible with the backend's in-memory, one-job worker model.

## Capabilities

### New Capabilities

- `single-container-runtime`: Serve the frontend and research API from one runnable image and one externally exposed HTTP port.

### Modified Capabilities

None.

## Impact

Changes the FastAPI application setup, production Docker build, runtime startup command, and deployment documentation. The existing API paths, graph contract, frontend behavior, CLI, and local two-process development flow remain supported. The runtime image will include Python dependencies and compiled frontend assets; it will not include development dependencies, source secrets, or a second externally required service.
