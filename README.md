# Scinapse — explore a paper field as a layered graph

Hackathon prototype for the **Pre-GTC HCLS Hackathon** (*Research Paper Discovery*):
given a few seed papers, build an interactive graph that shows how the field evolved
around them — newest relevant work at the top, seeds at the bottom, at most 3
citation layers in between.

Open **`scinapse_prototype.ipynb`** (fully executed, outputs included) or open
**`scinapse_graph.html`** directly for just the rendered graph.

## How to read the graph

- **Y axis = publication year** — newest at the top, seeds anchor the bottom.
- **Node color = venue quality**: red (journal publishes a suspicious number of
  papers/year — paper-mill territory) → gray → green (normal specialist venue).
  **Seeds are constant orange.** Exact numbers always in the tooltip and table.
- **Edges = reason for relevance** (hover for details, width = strength):
  blue solid = *cites* (arrow points at what it cites) · amber dashed = *abstract
  similarity* · pink dotted = *shared author*.
- **Click a node** to copy its DOI link.

## Run it

```bash
python -m pip install pandas numpy scikit-learn networkx pyvis openai
jupyter lab scinapse_prototype.ipynb     # or run headless:
python -m nbconvert --to notebook --execute --inplace scinapse_prototype.ipynb
```

No API keys required (Semantic Scholar + OpenAlex only; every response is cached
under `.scinapse_cache/`, so reruns are instant). Set a **Token Factory** key in the
notebook to switch TF-IDF → real embeddings and template → LLM relevance
explanations.

## Explore

- `more()` — load additional candidates per layer on demand (graph starts sparse)
- `inspect("id8")` — full card for a paper (metadata, quality, evidence, abstract)
- `expand("id8")` — re-grow the graph around a promising paper
- `reset_explore()` — back to the original seeds

## Pipeline

seeds (DOIs) → forward-citation BFS ×3 with score-based pruning
(multi-seed hits, recency, influence, author overlap) → top-entry layer (latest by
seed authors / by topic — papers too new to have citations) → venue-quality
enrichment → similarity + author edges → relevance explanations → pyvis graph +
results table.

## Data sources & honest limits

- **Semantic Scholar Graph API** — discovery (citations, author feeds, search,
  abstracts). Shared pool: the notebook paces and retries; expect occasional 429s.
- **OpenAlex** — venue statistics for the quality heuristic, via free
  single-record endpoints only (query endpoints are credit-rationed per IP).
- Quality is a **venue heuristic** (papers/year + retraction flag + flagship floor),
  not a verdict on any paper; preprint servers show as gray "unknown".
- Candidate windows are recency-sliced (deliberate frontier bias); older
  high-volume followers of a seed can be missed.
