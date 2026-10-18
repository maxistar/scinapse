## Context

See `proposal.md` for motivation and `specs/single-container-runtime/spec.md` for the behavior contract. The current production Dockerfile builds the Vite frontend into an Nginx-only image. `src/scinapse/api.py` exposes the FastAPI application and keeps one in-memory worker and job store. The frontend already uses relative `/api` URLs; Vite proxies those URLs to port 8000 only during local development.

## Goals / Non-Goals

**Goals:**
- Produce one image with the Python runtime, compiled frontend assets, and the graph example needed by the frontend build.
- Serve the frontend and API from one origin and one configurable public port.
- Preserve `scinapse.api:app` and the existing two-process local workflow.
- Keep runtime credentials outside the image and expose a health endpoint suitable for hosting checks.

**Non-Goals:**
- Adding a persistent queue, database, or multi-instance coordination.
- Increasing the backend's one-job concurrency or changing API semantics.
- Removing the standalone frontend image or the direct CLI pipeline.
- Adding Tavily integration.

## Decisions

1. **Use a production FastAPI wrapper for static files.** Add a small production entrypoint that creates the existing API app and mounts the compiled Vite `dist` directory at `/` with HTML fallback. API routes are registered before the static mount, so `/api/*` remains authoritative. This avoids running Nginx and Uvicorn as two processes in one container and keeps one process, one port, and one lifecycle.
2. **Use a multi-stage Node/Python build.** A Node stage runs `npm ci` and `npm run build` with `graph.json` available at the repository-relative path expected by the frontend. A Python stage installs the locked production environment with `uv` and the project package. The final Python runtime copies only the virtual environment, application package, compiled assets, and required bundled graph data.
3. **Run one Uvicorn process.** The container starts the production wrapper on `0.0.0.0` and the hosting platform's port. Do not use multiple workers because the current API stores jobs in process memory and deliberately serializes provider work.
4. **Keep local development unchanged.** `uv run uvicorn scinapse.api:app --host 127.0.0.1 --port 8000` and Vite's `/api` proxy remain the local path. The production wrapper is only the image entrypoint.
5. **Use environment-only runtime configuration.** `.env` stays ignored and is not copied into the image. The hosting platform injects `NEBIUS_API_KEY`, `S2_API_KEY`, `SCINAPSE_SMOKE`, `SCINAPSE_NO_LLM`, and `SCINAPSE_MAILTO` as needed. `/api/health` remains the health-check target.

## Risks / Trade-offs

- **Python serves static assets** -> This is appropriate for the single-instance competition deployment; a higher-traffic deployment can later place a CDN or reverse proxy in front without changing API paths.
- **In-memory jobs disappear on restart** -> Document the limitation and keep one worker; persistent job storage is outside this change.
- **Final image is larger than the current Nginx-only image** -> Copy only production dependencies and build output; the image still removes Node tooling from the runtime.
- **SPA fallback can mask missing asset paths if configured too broadly** -> Mount static files after API routes and verify root, asset, and API paths separately.

## Migration Plan

Build the unified image from the repository root, run it with the host-provided port mapping and environment variables, then verify `/api/health`, the frontend root, and a complete exploration job. Existing local commands and the standalone frontend image remain available for rollback. Deployment rollback is a switch back to the prior image tag.
