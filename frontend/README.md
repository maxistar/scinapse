# Scinapse research explorer

A React + TypeScript frontend for the repository's large fictional research graph dataset: 40 papers and 120 relationships. The quality filter uses each paper’s overall research-assessment score.

## Run locally

```sh
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite. Run `npm run build` for a production build, `npm run preview` to serve it, and `npm test` for the graph-selection and timeline checks (Node.js 22.18+ or 24+).

## Run with Docker

Build the production image from the repository root so the build can include the root dataset:

```sh
docker build -f frontend/Dockerfile -t scinapse-frontend .
docker run --rm -p 8080:80 scinapse-frontend
```

Open <http://localhost:8080>. The dataset is bundled during the image build, so rebuild the image after changing `sample_response.large.json`.

## Research setup

New sessions open a minimal search page. Enter a question or expand Starting papers to select matching fictional papers by title, author, ID or URL, or save external DOI/PMID/URL/title references for later lookup. The sample shortcut loads the original question and seeds. The graph displays the submitted query as read-only text. Clicking the Scinapse logo returns to a blank search page to begin a new exploration. Submitting creates a new research session; the previous query cannot be edited in place. Inputs and chosen seeds persist in local browser storage. Export includes the research inputs and the original assessment context.

This is a frontend demo: external references remain visibly pending, no live lookup or discovery runs, and existing relevance scores and relationships are not recalculated for the new query. Selected sample seeds control the graph's blue seed styling and starting-paper filter.

## Data and interactions

The application imports `../sample_response.large.json` directly; there is no copied dataset. Reload after external JSON changes. No backend, API keys, live discovery, or generated assessments are used.

- The initial view is a full-screen timeline. Single-click selects a paper and opens its information, or highlights an edge. Focus mode is opt-in: use Focus selection, the expand icon in the paper inspector, or double-click a paper/edge to bring its neighbourhood or endpoints forward. The overview remains mounted, dimmed and inert, with its viewport unchanged. Escape, the floating close icon or the backdrop dismiss focus.
- Foreground cards use fixed readable dimensions, retain year order, relevance colors, blue seeds and display-score line widths, and automatically fit within the window without scrollbars. Compact cards omit the score/action strip; click a card for information or double-click to explore its neighbourhood. Larger neighbourhoods can be zoomed and panned with the icon controls. Empty year gaps are condensed only in focus mode. Foreground papers are highlighted through their border, without status labels. Single-click a foreground card to inspect it; double-click it to explore its neighbourhood. The focus window has no header or footer. Details stay optional, including in edge focus.
- Selecting a paper highlights its direct neighbours in the currently enabled relationship types and fades unrelated papers. This applies to both overview and focus mode. Edges connect at the centers of card sides; longer curves route around intermediate rows.
- Minimum paper quality filters by `research_assessment.overall_score` on a 0–100 slider. Any includes unassessed papers; a positive minimum excludes unassessed candidate papers. Seed papers bypass the quality threshold and remain visible regardless of their score; collection and search filters still apply.
- Publication year determines vertical position, with proportional spacing and newest work at the top. Filtering retains each remaining paper's original position.
- Paper cards use a compact layout on an ivory canvas. Starting papers have a distinct blue fill and a Seed label. Select a paper to inspect relevance, evidence, quality dimensions, and publication status.
- Hovering over a connection shows its reasoning in a readable tooltip, in both overview and focus mode. Keyboard focus also reveals it; Escape dismisses it.
- Relationship filters apply before representative-edge selection. Each unordered paper pair shows its highest display score, ties use edge ID, and citation direction is preserved. The + badge opens that pair in focus; relationship evidence remains available through disclosures in the paper Connections tab.
- The sample's `display_score.value` determines both the representative relationship and its line width: `1 + score * 4.5` for valid 0–1 scores, with a thin fallback for missing or invalid values. Raw relationship strength remains available as evidence and does not control thickness.
- Node colors use `relevance.score` on a 0–1 scale: low relevance is red, medium is amber, and high relevance is green. Seed papers remain blue; their dot indicates relevance. Null or invalid relevance remains neutral. Paper quality remains a separate assessment in the Quality tab; it does not drive node colors. The Legend explains these visual encodings.
- Search matches titles, topics, methods, and authors. The Filters popover includes the starting collection and saved shortlist.
- Save state persists in browser local storage. Hiding papers affects the current view; connected hidden papers can be revealed from a neighbour. Reset restores the graph and filters, retaining saved papers.
- The legend, research question, and relationship evidence are disclosed on demand. The More options menu contains help, reset, and export.
- Export downloads the filtered subgraph with current saved state.

All source links and identities are fictional placeholders, and the interface labels them as demo data. Missing quality evidence is shown as unknown or not assessed.

The current layout targets small research collections. Larger collections will need horizontal collision handling, clustering, and incremental server-backed expansion. This version provides a local frontend only and does not deploy automatically.
