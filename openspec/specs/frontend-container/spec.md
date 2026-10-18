## Purpose

Provide a repeatable way to package and serve the existing research explorer frontend from a repository checkout using a container image.

## Requirements

### Requirement: Buildable frontend image
The project SHALL provide a documented command that builds a runnable frontend image from a repository checkout containing `sample_response.large.json`, without requiring host-installed frontend dependencies.

#### Scenario: Build from clean checkout
- **WHEN** a user runs the documented build command from a checkout with Docker available and no local `frontend/node_modules` directory
- **THEN** the build succeeds and produces a runnable image containing the compiled frontend

### Requirement: Serve the existing application
The image SHALL serve the production frontend over HTTP on a documented container port, including the research graph derived from `sample_response.large.json` at build time.

#### Scenario: Run the image locally
- **WHEN** a user starts the image with the documented port mapping and opens the local address
- **THEN** the research explorer loads and displays the bundled sample graph

#### Scenario: Dataset changes before rebuilding
- **WHEN** `sample_response.large.json` changes and a user rebuilds the image
- **THEN** the rebuilt frontend includes the updated dataset
