# AGENTS.md

Guidance for coding agents working in this repository.

## What this is

Scinapse turns a small set of seed papers (DOIs) plus a research question into a
research-paper discovery graph — a JSON document in the shape of
`sample_response.json` (the contract). The pipeline fetches from Semantic
Scholar + OpenAlex, builds three edge types, computes scores, and optionally
runs LLM relevance assessment via Nebius Token Factory.

## Commands

```bash
uv run pytest                      # tests (network-free)
uv run scinapse build --seed <DOI> --question "..." --out graph.json --smoke
uv run scinapse check graph.json   # validate output against the contract
```

- Always use `uv run` (deps are managed by uv; `.venv/` is committed to nothing).
- `--smoke` = tiny profile (1 layer, small caps, 8 LLM calls) for cheap e2e verification.
- `--no-llm` skips the Token Factory step entirely (no `NEBIUS_API_KEY` needed).
- Python >= 3.10. No linters/formatters configured; match existing style
  (module docstring first line, `from __future__ import annotations`, compact code).

## Pipeline (src/scinapse/)

`pipeline.py:run` orchestrates, in order:

1. `discovery.fetch_seeds` — resolve seed DOIs via S2
2. `discovery.expand_layers` — forward-citation BFS (papers *citing* the layer below), top-K/layer
3. `discovery.add_top_entry` — pin recent papers (default >= 2025) by seed authors / topic
4. `enrich.enrich_openalex` — venue quality, retraction, affiliations, topics
5. `similarity.build_similarity` — TF-IDF fallback, or Token Factory embeddings when `embed_model` is set
6. `edges` — exactly 3 edge types, one [0,1] strength each: `citation_overlap`, `shared_author`, `similar_to`
7. `discovery.finalize` — composite node scores + evidence lines
8. `assess.assess_all` — one JSON-mode chat call per node (capped by `llm_limit`), fills the 4 relevance-rubric dimensions. Escalating token budget (2500 -> 6000) with length-truncation retry — reasoning models burn the budget before emitting content; never cache empty replies.
9. `serialize.build_document` — emit the contract shape; `ids.py` mints sequential deterministic ids

Supporting modules: `httpjson.py` (disk-cached paced HTTP), `s2.py` / `openalex.py`
(API clients), `config.py` (BuildConfig, DOI normalization, dotenv, exploration_id),
`checker.py` (contract validation), `static_blocks.py` (assessment_policy etc. copied
from the sample), `warnings.py` (run diagnostics), `textutil.py` (shared text
normalizer — see contract section).

Invariants that were bugs once — keep them true:

- `shared_author` edges: match authors by OpenAlex ids exclusively when a paper is
  enriched, S2 ids only as fallback. Mixing both id spaces double-counts every
  author and inflates the Salton numerator.

## The contract (sample_response.json)

- `checker.py` validates structure **and semantics**: key order mirrors the sample,
  weighted-rubric relevance scores are recomputed, quotes must be contained in the
  source abstract/title, `display_score.value` must mirror edge strength, edge
  endpoints must exist.
- Quote containment is checked *after normalization* (`textutil.normalize_text`:
  casefold + whitespace collapse + NFKC + typographic punctuation folding), and the
  assessor uses the same function to pre-verify quotes. LLMs transcribe curly
  quotes / non-breaking hyphens — if you ever touch quote handling, keep assessor
  and checker on the one shared normalizer, never two.
- `tests/test_checker.py` is network-free and builds a minimal document in-memory —
  extend it when touching `serialize.py` or `checker.py`. If you change the document
  shape, update `sample_response.json` and the checker together.
- Missing evidence is represented as `null` + `"uncertain"` / `"insufficient_evidence"`
  — never invent scores.

## External API constraints (hard-won; respect them)

- **OpenAlex**: query/filter/list endpoints burn a shared 1000-credits/day pool that
  may already be dry (check `x-ratelimit-remaining`). **Single-object GETs
  (`/works/W…`, `/works/doi:…`, `/sources/S…`) cost 0 credits — use only those.**
  On `/sources`, `h_index` is not selectable (400); it lives in `summary_stats`.
  `counts_by_year[0]` is the current partial year — use the last complete one.
- **Semantic Scholar** (unauthenticated): shared pool 429s often; keep
  `s2_min_interval=1.25`s + exponential backoff. `/paper/{id}/citations` returns
  citers newest-first. `/author/{id}/papers` returns `{offset, next, data}`.
  `/paper/search` rate-limits hardest.
- All HTTP goes through `httpjson.Http` → `.scinapse_cache/` (gitignored). Reruns
  are cheap; don't bypass the cache or the pacing.
- LLM access is OpenAI-compatible at `https://api.tokenfactory.nebius.com/v1/`
  with `NEBIUS_API_KEY` (`.env`, gitignored). `S2_API_KEY` is optional.

## Repo quirks

- No notebooks in the tree by design. The prototype the package was ported from
  — including the pyvis HTML renderer and `inspect()`/`expand()`/`more()` explore
  helpers, none of which are ported to the package — is archived on the
  `jupyter_ui_mock` branch (kernel: `scinapse-310`).
- `*:Zone.Identifier` files are Windows download-tracking stubs; gitignored
  (`*:Zone.Identifier`) — they reappear when files are copied from the Windows side;
  safe to delete on sight.
- `graph_*.json` outputs are gitignored on purpose.
