# Scinapse

Scinapse is a research-paper discovery tool that turns a small collection of seed papers and a research question into a ranked, traceable discovery graph. It combines citation expansion, metadata enrichment, similarity scoring, and optional LLM relevance assessments with an interactive React explorer.

This project was created as part of a research and AI application competition.

<br />

## The problem

Researchers often have a collection of papers relevant to their topic but struggle to find more through keyword searches alone. Scinapse takes that existing collection as a starting point and discovers additional relevant publications.

## The challenge

The app helps a researcher move from known papers to a ranked, traceable set of new ones. Each recommendation includes useful metadata, relationship evidence, source links, and an explanation of why it may be relevant.

## How Scinapse works

```text
Seed DOIs + research question
              |
              v
    Semantic Scholar discovery
              |
              v
   Citation and author expansion
              |
              v
     OpenAlex enrichment
              |
              v
   Similarity and graph scoring
              |
              v
 Optional Nebius assessments
              |
              v
       JSON graph contract
              |
              v
       React graph explorer
```

The pipeline produces a validated JSON document containing paper nodes, relationship edges, relevance scores, evidence, warnings, and assessment details. The frontend presents that document as a timeline and connected-paper exploration interface.

## Competition approaches

Scinapse combines several of the suggested approaches:

- Follow citation and reference networks to find papers connected to multiple seed publications.
- Use TF-IDF similarity by default, with optional embeddings from Nebius Token Factory.
- Use Nebius Token Factory for structured relevance assessment, ranking support, and explanations.
- Combine retrieval, ranking, evidence inspection, filters, and human review in an interactive workflow.

The graph pipeline currently uses Semantic Scholar and OpenAlex for discovery and metadata enrichment. Tavily is a supported competition integration target for agentic web context and source enrichment; live Tavily lookup is not required by the local demo dataset.

## Services and APIs

- [Nebius Token Factory](https://hackathons.techeurope.io/start-here/setup.md) — OpenAI-compatible LLM and embedding inference.
- [Tavily](https://www.tavily.com/) — agentic search for web context and supporting sources.
- [Semantic Scholar](https://www.semanticscholar.org/product/api) — seed resolution and citation discovery.
- [OpenAlex](https://docs.openalex.org/) — paper, author, venue, topic, and reference metadata.

The repository caches HTTP responses locally and applies pacing and retry behavior for external API calls. API keys are read from environment variables and are never committed.

## Run the research pipeline

The Python package requires Python 3.10 or newer and uses `uv` for dependency management.

```sh
uv sync

# Build a small, inexpensive graph for verification
uv run scinapse build \
  --seed 10.1038/s41586-020-2649-2 \
  --question "How can machine learning improve scientific discovery?" \
  --out graph.json \
  --smoke

# Skip Nebius assessments when an API key is unavailable
uv run scinapse build \
  --seed 10.1038/s41586-020-2649-2 \
  --question "How can machine learning improve scientific discovery?" \
  --out graph.json \
  --smoke \
  --no-llm

# Validate a generated graph
uv run scinapse check graph.json
```

Set `NEBIUS_API_KEY` to enable Token Factory assessments. `S2_API_KEY` is optional. The command accepts multiple `--seed` values, for example:

```sh
uv run scinapse build \
  --seed 10.1038/s41586-020-2649-2 \
  --seed 10.1126/science.aar6847 \
  --question "What methods improve scientific discovery?" \
  --out graph.json
```

Run the network-free test suite with:

```sh
uv run pytest
```

## Run the frontend locally

The frontend is a React and TypeScript application powered by Vite. It includes the repository's demo graph from `sample_response.large.json` and does not require a backend for the local demo.

```sh
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite. Other useful commands are:

```sh
npm run build
npm test
```

The interface supports paper search, seed selection, timeline filtering, relationship inspection, focus views, saved papers, local browser state, and graph export. See [frontend/README.md](frontend/README.md) for the full interaction guide.

## Run the frontend with Docker

Build from the repository root so Docker can include `sample_response.large.json`:

```sh
docker build -f frontend/Dockerfile -t scinapse-frontend .
docker run --rm -p 8080:80 scinapse-frontend
```

Open <http://localhost:8080>. The image uses a multi-stage Node and Nginx build. The demo dataset is bundled at build time, so rebuild the image after changing `sample_response.large.json`.

## Repository structure

```text
src/scinapse/             Python discovery, enrichment, scoring, assessment, and validation pipeline
frontend/                 React/Vite research graph explorer
sample_response.json      Small graph contract example
sample_response.large.json Demo frontend dataset
tests/                    Network-free Python tests
graph.json                Example/generated graph output
```

## Deliverable and documentation

The competition deliverable is a working research discovery experience with a public source repository, setup instructions, documented APIs and tools, and enough technical detail for evaluation. The repository contains the pipeline contract, checker, frontend interaction documentation, Docker packaging, and tests needed to inspect and run the project.

All links and identities in the bundled demo graph are fictional placeholders. A production deployment should connect the pipeline output to a hosted backend and serve the frontend separately from the model endpoint, with API credentials stored in the deployment environment.


# Quick Start


Run the API and React application using [frontend/README.md](frontend/README.md). The backend remains available as `uv run scinapse build` and `uv run scinapse check`.
