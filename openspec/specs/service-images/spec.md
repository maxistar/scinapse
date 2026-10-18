## Purpose

Provide independently deployable frontend and backend images for Kubernetes while retaining the existing unified image for hosting environments that require one container.

## Requirements

### Requirement: Backend-only image

The project SHALL provide a documented backend image that starts the existing FastAPI API on port 8000 without bundling or serving the compiled frontend.

#### Scenario: Backend image starts from a clean checkout

- **WHEN** a user builds the backend image from the repository root and starts it with Docker
- **THEN** the container starts the API on port 8000 and `/api/health` returns a successful health response

#### Scenario: Backend receives runtime configuration

- **WHEN** provider credentials and `SCINAPSE_*` settings are supplied as container environment variables
- **THEN** the backend reads them at runtime without requiring `.env` or secrets in the image

### Requirement: Frontend-only image

The project SHALL provide a documented frontend image that builds the Vite application from a clean checkout and serves the compiled static application over HTTP.

#### Scenario: Frontend image serves the production application

- **WHEN** a user builds and starts the frontend-only image with the documented port mapping
- **THEN** the application shell and bundled example graph are served successfully

#### Scenario: Frontend API requests remain routable

- **WHEN** the deployed frontend makes requests under `/api`
- **THEN** those requests retain their same-origin paths so a later Kubernetes router can direct them to the backend Service

### Requirement: Unified image compatibility

The existing unified image SHALL remain buildable and runnable after the split image definitions are introduced.

#### Scenario: Existing unified deployment continues to work

- **WHEN** a user builds the documented unified image and starts it with its existing runtime configuration
- **THEN** the frontend and backend remain available from the same public port with unchanged API paths

#### Scenario: Image variants are independently documented

- **WHEN** a user reads the container documentation
- **THEN** it identifies the frontend-only, backend-only, and unified image build and run commands and their intended deployment use
