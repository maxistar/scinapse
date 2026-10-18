## 1. Unified Application Runtime

- [x] 1.1 Add a production FastAPI entrypoint that mounts the compiled frontend at `/` while preserving all existing `/api` routes; verify a test client receives the frontend entry document and `/api/health` from the same app.
- [x] 1.2 Ensure static-file mounting has safe SPA fallback and does not intercept API paths; verify frontend asset requests, missing API routes, and health responses return the expected status codes.

## 2. Production Image

- [x] 2.1 Replace the frontend-only Docker build with a multi-stage image that compiles the Vite app, installs locked Python runtime dependencies, copies the backend and compiled assets, and starts one Uvicorn process on the configured public port; verify a clean root-context `docker build` succeeds.
- [x] 2.2 Keep secrets and profile settings runtime-configurable and add a container health check or documented health probe for `/api/health`; verify the image starts without `.env` and reports assessment availability from environment configuration.

## 3. Documentation and Verification

- [x] 3.1 Update root and frontend README instructions for the unified image, public port, environment variables, local two-service development, and the single-worker/in-memory job limitation; verify commands and endpoints match the implementation.
- [x] 3.2 Run Python and frontend tests, build the image, start it, and verify the frontend root, `/api/health`, and one API request are served from the same port; record any provider-dependent limitation separately from container verification.
