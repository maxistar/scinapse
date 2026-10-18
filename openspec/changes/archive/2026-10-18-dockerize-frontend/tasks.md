## 1. Container Build

- [x] 1.1 Add `frontend/Dockerfile` with a Node 24 build stage and static Nginx runtime; verify `docker build -f frontend/Dockerfile -t scinapse-frontend .` succeeds from the repository root.
- [x] 1.2 Add root `.dockerignore` to exclude host dependencies, build output, VCS data, and unrelated files while retaining `frontend/` and `sample_response.large.json`; verify the root-context Docker build still succeeds without host `frontend/node_modules`.

## 2. Usage and Verification

- [x] 2.1 Document the root-context build command, `docker run --rm -p 8080:80 scinapse-frontend`, local URL, and dataset rebuild behavior in `frontend/README.md`; verify the documented commands and paths match the Dockerfile.
- [x] 2.2 Run the image and verify `http://localhost:8080` serves the application and displays the bundled sample graph; confirm the existing `npm run build` still succeeds.
