## Purpose

Allow the complete Scinapse web application to run from one container image and one externally exposed HTTP port when the hosting platform cannot deploy separate frontend and backend services.

## ADDED Requirements

### Requirement: Unified HTTP runtime
The project SHALL provide one runnable image whose public HTTP port serves both the compiled frontend at `/` and the existing research API under `/api`.

#### Scenario: Frontend and API share one origin
- **WHEN** a user starts the unified image and opens its public URL
- **THEN** the frontend loads from `/`, and browser requests to `/api/health` and `/api/explorations` reach the backend through the same origin

#### Scenario: API routes remain compatible
- **WHEN** a client calls the existing exploration, status, history, or graph endpoints through the unified image
- **THEN** the endpoint paths, request validation, response statuses, and graph response shape remain unchanged

### Requirement: Production image is self-contained
The unified image SHALL contain the compiled frontend and all runtime Python dependencies needed by the FastAPI service, without requiring host-installed Node packages, a second container, or source secrets.

#### Scenario: Build from a clean checkout
- **WHEN** a user builds the documented image from the repository root with Docker available
- **THEN** the build installs dependencies in intermediate stages, compiles the frontend, and produces one runnable image

### Requirement: Runtime configuration and health
The unified runtime SHALL accept provider credentials and profile settings through environment variables and SHALL expose `/api/health` for platform health checks.

#### Scenario: Start without provider credentials
- **WHEN** the container starts without `NEBIUS_API_KEY`
- **THEN** the health endpoint reports the service as available and indicates that assessments are disabled, while the API remains usable for discovery attempts

#### Scenario: Runtime secrets are supplied externally
- **WHEN** a hosting platform injects `NEBIUS_API_KEY`, `S2_API_KEY`, or `SCINAPSE_*` variables at container startup
- **THEN** the backend reads those values without requiring `.env` to be copied into the image
