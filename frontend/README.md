# Scinapse research explorer

A React + TypeScript frontend for the repository's backend-generated `graph.json`: 35 papers and 56 relationships (51 visible paper pairs). The relevance filter uses each paper’s `relevance.score`.

## Run both services locally

Requires Python 3.10+, uv, and Node.js 22.18+ or 24+. From the repository root:

```sh
uv sync --dev
uv run uvicorn scinapse.api:app --host 127.0.0.1 --port 8000
```

In another terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open <http://127.0.0.1:5173>. Vite forwards `/api` to the backend on port 8000. API health is at `/api/health`; interactive API documentation is at <http://127.0.0.1:8000/docs>.

Copy `.env.example` to `.env` in the repository root and supply `NEBIUS_API_KEY` to enable relevance assessment. `S2_API_KEY` is optional but can improve shared-pool rate limits. Keys stay on the backend. With no Nebius key, discovery still works and relevance remains unassessed. Restart the backend after changing environment settings.

`SCINAPSE_SMOKE=1` is the default quick profile (one expansion layer, smaller caps). Set it to `0` for the standard pipeline. `SCINAPSE_NO_LLM=1` explicitly skips assessments. Discovery can take minutes because requests use the pipeline's existing cache, pacing and backoff.

Run `uv run pytest`, `uv run scinapse check graph.json`, `npm test` and `npm run build` (the npm commands run inside `frontend`). The original `scinapse build` CLI remains available.

## Search and API flow

Enter a question (3–2000 characters) and one to ten starting DOIs. DOI URLs are accepted and duplicates are removed. Papers from the example collection can be selected by title; their DOI is submitted. External title-only lookup and PMID resolution are not yet supported.

Use **Research history** on the search page or in the graph’s More options menu to list tasks. The dialog refreshes automatically, filters by status, opens completed graphs, downloads full graph JSON, and resumes progress for running tasks. Empty, offline and expired-result states are handled explicitly.

Task inspection APIs:

- `GET /api/explorations`: retained tasks, newest first, with `tasks` and `total`.
- `GET /api/explorations?status=completed`: filter by queued, running, completed or failed.
- `GET /api/explorations/{id}`: status, question, stage, timestamps and links.
- `GET /api/explorations/{id}/graph`: full graph JSON for completed tasks; HTTP 409 otherwise, 404 for missing tasks.

Task summaries include `status_url` and a `graph_url` only when completed. Lists do not embed graph data. The retention and restart limitations below apply.

The frontend submits `POST /api/explorations` with `{"question":"...","seeds":["10.1126/science.aad0501"]}`. The server returns HTTP 202 with a job ID. The frontend polls `GET /api/explorations/{id}` for queued/running/completed/failed status and the real pipeline stage, then loads `GET /api/explorations/{id}/graph`. The returned graph replaces the example; its question, seeds, metadata, evidence and warnings are authoritative. Exports use the active graph, and saved papers are isolated by its exploration ID.

The UI handles validation, unreachable servers, failed jobs and expired sessions, with retry. Refresh resumes polling the current tab's job. Going back to search stops waiting in the browser; the server's current job continues. One job runs at a time to respect provider pacing; additional submissions return 409. Up to 20 completed jobs are kept in memory. Restarting the backend loses them; expired sessions require a new search. Use one API process/worker for this local implementation; a persistent shared queue is needed before scaling.

“Open example graph” explicitly opens the bundled `../graph.json`, without invoking discovery. It remains available when external providers are down. Search never silently falls back to the example.

## Frontend Docker image

```sh
docker build -f frontend/Dockerfile -t scinapse-frontend .
docker run --rm -p 8080:80 scinapse-frontend
```

The existing image serves the frontend and bundled example at <http://localhost:8080>. Live search requires an `/api` reverse proxy to the Python service; this local integration uses Vite's proxy. The image is not a combined backend deployment. Rebuild after changing the bundled example.

## Data and interactions

The application imports `../graph.json` directly; there is no copied dataset. Reload after external JSON changes. The file is used only for the explicit example action. Live searches render the JSON returned by the API.

- Opening the artifact shows a full-screen timeline. Single-click selects a paper and opens its information, or highlights an edge. Focus mode is opt-in: use Focus selection, the expand icon in the paper inspector, or double-click a paper/edge to bring its neighbourhood or endpoints forward. The overview remains mounted, dimmed and inert, with its viewport unchanged. Escape, the floating close icon or the backdrop dismiss focus.
- Foreground cards use fixed readable dimensions, retain year order, relevance colors, blue seeds and display-score line widths, and automatically fit within the window without scrollbars. Compact cards omit the score/action strip; click a card for information or double-click to explore its neighbourhood. Larger neighbourhoods can be zoomed and panned with the icon controls. Empty year gaps are condensed only in focus mode. Foreground papers are highlighted through their border, without status labels. Single-click a foreground card to inspect it; double-click it to explore its neighbourhood. The focus window has no header or footer. Details stay optional, including in edge focus.
- Selecting a paper highlights its direct neighbours in the currently enabled relationship types and fades unrelated papers. This applies to both overview and focus mode. Edges connect at the centers of card sides; longer curves route around intermediate rows.
- Minimum relevance filters by `relevance.score` on a 0–100 slider. Any includes unassessed papers; a positive minimum excludes unassessed candidate papers. Seed papers bypass the relevance threshold regardless of their score; collection and text-search filters still apply. If all relevance scores are missing, the slider explains that assessments are needed. Research quality remains separate in the Quality tab.
- Publication year determines vertical position, with proportional spacing and newest work at the top. Filtering retains each remaining paper's original position.
- Paper cards use a compact layout on an ivory canvas. Starting papers have a distinct blue fill and a Seed label. Select a paper to inspect relevance, evidence, quality dimensions, and publication status.
- Hovering over a connection shows its reasoning in a readable tooltip, in both overview and focus mode. Keyboard focus also reveals it; Escape dismisses it.
- Relationship filters apply before representative-edge selection. Each unordered paper pair shows its highest display score, ties use edge ID, and citation direction is preserved. The + badge opens that pair in focus; relationship evidence remains available through disclosures in the paper Connections tab.
- Each edge’s `display_score.value` determines both the representative relationship and its line width: `1 + score * 4.5` for valid 0–1 scores, with a thin fallback for missing or invalid values. Raw relationship strength remains available as evidence and does not control thickness.
- Node colors use `relevance.score` on a 0–1 scale: low relevance is red, medium is amber, and high relevance is green. Seed papers remain blue; their dot indicates relevance. Null or invalid relevance remains neutral. Paper quality remains a separate assessment in the Quality tab; it does not drive node colors. The Legend explains these visual encodings.
- Search matches titles, topics, methods, and authors. The Filters popover includes the starting collection and saved shortlist.
- Save state persists in browser local storage. Hiding papers affects the current view; connected hidden papers can be revealed from a neighbour. Reset restores the graph and filters, retaining saved papers.
- The legend, research question, and relationship evidence are disclosed on demand. The More options menu contains help, reset, and export.
- Export downloads the filtered subgraph with current saved state.

Backend relationships are Citation overlap, Shared authors, and Semantic similarity. Citation overlap can combine direct citation records and reference-list overlap; it is not labeled as a direct citation. The legend and filters use the types present in the artifact. Author-list evidence shows author names; reference-list evidence shows referenced papers or an explicit empty-record message. Evidence displays its supplied provenance.

The compact notices control exposes retrieval warnings, including rate limits and partial assessments, and links paper-specific notices to the corresponding node. Missing quality evidence is shown as unassessed, never inferred from institutional prestige.

The current layout targets small research collections. Larger collections will need horizontal collision handling, clustering, and incremental server-backed expansion. This integration runs locally and does not deploy automatically.
