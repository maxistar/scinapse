## Context

The repository currently has one multi-stage definition at `frontend/Dockerfile`. It builds the Vite app and Python environment together, then starts `scinapse.web:app`, which serves both the frontend and `/api`. The backend package is rooted at `src/`, while the frontend build expects `frontend/package-lock.json` and the repository-level `graph.json`.

The split images must preserve the existing API contract and same-origin `/api` paths. Kubernetes routing is a later change, so the frontend image should serve static files without embedding backend connectivity assumptions.

## Goals / Non-Goals

**Goals:**

- Produce a backend-only image with the Python runtime and FastAPI API.
- Produce a frontend-only image with the compiled Vite assets and SPA fallback behavior.
- Preserve the unified image as a separately named, tested build path.
- Keep provider credentials outside all images.
- Make each image suitable for tagging and pushing to a container registry.

**Non-Goals:**

- Kubernetes Deployments, Services, Ingress, or registry resources.
- Durable job storage, worker extraction, or API scaling changes.
- Changes to API routes, frontend request paths, or graph contracts.

## Decisions

### Keep the unified image as a renamed sibling

Move the current definition to `frontend/Dockerfile.unified` with its stages and `scinapse.web:app` command intact. The new frontend-only definition occupies `frontend/Dockerfile`, and documentation must use the explicit `.unified` path for the legacy deployment. This preserves the image behavior while making the default frontend Dockerfile appropriate for Kubernetes.

Alternative considered: keep the unified file at `frontend/Dockerfile` and name the split frontend file differently. This avoids changing an existing build path but conflicts with the desired conventional frontend path and makes future Kubernetes commands less clear.

### Use separate runtime bases for the services

The backend image will use the existing `uv` dependency lockfile workflow and a slim Python runtime, expose port 8000, and start `scinapse.api:app`. It will not copy frontend assets. The frontend image will use a Node build stage followed by a small Nginx runtime, expose port 80, and serve the Vite output plus `graph.json` content compiled into that output.

Alternative considered: use the Python static server for the frontend image. Nginx provides a smaller, purpose-built static runtime and SPA fallback without coupling the frontend image to Python dependencies.

### Leave `/api` routing to the deployment layer

The frontend image will retain absolute same-origin `/api` requests and will not proxy to a hard-coded backend hostname. A later Ingress or gateway can route `/api` to the backend Service while `/` goes to the frontend Service.

Alternative considered: bake an Nginx reverse proxy into the frontend image. That would require a runtime backend address and duplicate Kubernetes routing responsibility.

### Validate images through observable HTTP checks

The backend health check will call `/api/health`. The frontend check will request `/` and verify the static server responds. Build verification will run from a clean checkout and will include the existing Python and frontend test suites where practical.

## Risks / Trade-offs

- **[Existing host points at `frontend/Dockerfile`]** → Update the initial hosting configuration to use `frontend/Dockerfile.unified` before switching the default file; document both commands and test the unified image after the rename.
- **[Frontend image cannot reach `/api` by itself]** → This is intentional; the Kubernetes routing change must provide `/api` routing on the same public origin.
- **[Nginx SPA fallback is misconfigured]** → Add and test an explicit Nginx configuration that falls back unknown frontend paths to `index.html` while leaving `/api` to the deployment router.
- **[Registry or cluster architecture differs from local Docker]** → Keep images free of host secrets, use standard Linux bases, and document registry tagging without assuming a specific registry implementation.
- **[Unified and split builds drift]** → Keep the unified Dockerfile unchanged except for its filename and include all three image builds in verification.

## Migration Plan

1. Update the temporary hosting configuration to build `frontend/Dockerfile.unified`.
2. Rename the existing definition and add the backend and frontend-only definitions.
3. Build and smoke-test `scinapse-unified`, `scinapse-backend`, and `scinapse-frontend` locally.
4. Push the split images to the selected registry; retain the unified image tag for rollback.
5. Roll back by pointing the temporary host back to the retained unified image tag if either split image fails.
