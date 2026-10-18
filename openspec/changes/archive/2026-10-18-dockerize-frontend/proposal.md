## Why

The frontend currently runs through local npm commands, so deploying it requires a separately prepared Node environment and manual build steps. A reproducible container image will make the existing static app straightforward to build and serve.

## What Changes

- Add a production Docker build for the React/Vite frontend and serve its compiled assets over HTTP.
- Build from the repository root so the existing import of `sample_response.large.json` remains valid.
- Exclude local dependencies, build output, and unrelated repository files from the Docker build context.
- Document the build, run, and verification commands in `frontend/README.md`.

## Capabilities

### New Capabilities

- `frontend-container`: Build and run the existing frontend as a self-contained production container image.

### Modified Capabilities

None.

## Impact

Adds a Dockerfile under `frontend/` and a root `.dockerignore`; updates `frontend/README.md`. The frontend source, browser behavior, dependencies, and local npm workflow remain unchanged. Docker is required only to build and run the image.
