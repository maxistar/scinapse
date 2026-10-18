## 1. Preserve the unified image

- [x] 1.1 Rename the existing unified definition to `frontend/Dockerfile.unified` without changing its stages, runtime command, or environment contract; verify `docker build -f frontend/Dockerfile.unified -t scinapse-unified .` succeeds.
- [x] 1.2 Update unified-image documentation and temporary-host instructions to use `frontend/Dockerfile.unified`; verify the documented command references an existing file.

## 2. Add the split image definitions

- [x] 2.1 Add the repository-root backend `Dockerfile` with locked Python dependencies, `scinapse.api:app`, port 8000, external runtime configuration, and a health check; verify the image starts and `/api/health` responds.
- [x] 2.2 Add the frontend-only `frontend/Dockerfile` with a clean Node build stage and static web runtime; verify the image serves `/` and the bundled example graph.
- [x] 2.3 Add the frontend static-server configuration needed for SPA fallback while leaving `/api` paths available for deployment routing; verify a client-side route returns the application shell.

## 3. Verify compatibility and documentation

- [x] 3.1 Build `scinapse-backend`, `scinapse-frontend`, and `scinapse-unified` from a checkout without host-installed dependencies; verify all three builds complete.
- [x] 3.2 Run backend tests and frontend tests/build; verify existing API paths, graph contract checks, and frontend production compilation remain green.
- [x] 3.3 Run smoke containers for the backend and frontend images with documented ports and runtime variables; verify backend health, frontend HTML, and same-origin `/api` request paths are observable.
- [x] 3.4 Document image tags, registry push examples, ports, health checks, and the unified-image rollback path in the root and frontend READMEs; verify the commands match the final Dockerfile paths.
