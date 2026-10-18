## Context

See `proposal.md` for motivation and `specs/frontend-container/spec.md` for the behavior contract. The Vite app's `frontend/src/App.tsx` imports `../../sample_response.large.json`; `npm run build` performs TypeScript checking and emits static assets to `frontend/dist`. There is no backend or client-side router. The current Vite development script binds to `127.0.0.1`.

## Goals / Non-Goals

**Goals:**
- Produce a production image from the existing lockfile and source without relying on host `node_modules`.
- Keep the image's runtime limited to serving compiled static assets.
- Preserve the dataset import path and existing local development workflow.

**Non-Goals:**
- Running Vite or hot reload inside Docker.
- Adding a backend, runtime dataset loading, or persistent server-side state.
- Publishing an image or defining deployment infrastructure.

## Decisions

1. **Use the repository root as Docker build context and `frontend/Dockerfile` as the Dockerfile.** This makes the root dataset available while leaving the relative import intact. Building with `frontend/` as context cannot access the parent JSON file; copying the dataset into the frontend would create a second source of truth.
2. **Use a multi-stage build.** A Node 24 Alpine builder runs `npm ci` using `frontend/package-lock.json`, copies the frontend and root dataset into matching relative paths, and runs `npm run build`. An Nginx Alpine runtime serves only `dist` on port 80. Serving the static result avoids shipping build tools and dependencies at runtime; running `vite preview` would retain Node for no application need.
3. **Add a root `.dockerignore`.** Exclude `.git`, `frontend/node_modules`, `frontend/dist`, and unrelated repo content while retaining `frontend/` and `sample_response.large.json`. This keeps the build context small and prevents host artifacts from entering the image. Keep the package files in a separate copy step so dependency installation can be cached when only source or data changes.
4. **Document root-level build and run commands in `frontend/README.md`.** Use `docker build -f frontend/Dockerfile -t scinapse-frontend .` and `docker run --rm -p 8080:80 scinapse-frontend`; explain that dataset changes require a rebuild. The browser's local storage remains browser-managed and may differ from the Vite origin because the port changes.

## Risks / Trade-offs

- **Dataset is embedded at build time** -> Document rebuilds after JSON changes; runtime updates are outside this change.
- **Public Google Fonts import still needs browser network access** -> The application remains functional with browser fallback fonts; this change does not bundle fonts.
- **Base image tags can change over time** -> Use maintained major/variant tags in the initial implementation and allow later digest pinning if deployment policy requires immutable builds.

## Migration Plan

Add the container files and README instructions, build the image from the repository root, and verify the served graph in a browser. Existing `npm run dev` and `npm run build` commands remain available. Rollback consists of stopping the container and using the existing local workflow.
