# Ideas

A scratchpad for anything worth exploring in Scinapse — features, experiments, directions. Nothing here is committed; it's a place to think out loud.

## Format

One idea per entry, roughly:

```
### <short title>
- **What:** one or two sentences
- **Why / motivation:** what problem it solves or what it unlocks
- **Status:** 💡 idea | 🔬 exploring | ✅ done | 🗑 dropped
```

---

## Ideas

### Paper connection strength across 3 dimensions
- **What:** Score how strongly two papers are connected along citation / author / semantic links, then fuse into one edge weight.
- **Citation:** direct cite = 1.0; bibliographic coupling and co-citation normalized (Salton `shared/√(a·b)` or Jaccard); 2-hop paths decay `0.5^(d-1)`. Combine with `max()` — they're alternative evidences, not additive.
- **Author:** overlap normalized by author-list size (Salton `|A∩B|/√(|A|·|B|)`) to kill 500-author-paper bias; IDF-weight each shared author by `log(N/n_author)` so rare co-authors count more.
- **Semantic:** embed title+abstract (SPECTER / SciNCL — trained on citation graphs, so similarity ≈ "would cite"), cosine similarity, then **percentile-rank within corpus** because raw cosines cluster in a narrow band.
- **Fusion:** percentile-rank each dimension to [0,1]; treat missing citation/author data as *unknown*, not zero; weighted sum starting at `0.4·C + 0.2·A + 0.4·S`; if labeled pairs appear, fit weights via logistic regression on the 3 features.
- **Why:** raw citation graphs are binary and sparse; combining normalized structural, social, and content evidence gives denser, more meaningful edges for graph analysis / visualization.
- **API-lean version** (OpenAlex only, ~1 query/paper): drop co-citation and path decay — keep bibliographic coupling `|refs(A)∩refs(B)|/√(|refs(A)|·|refs(B)|)` from `referenced_works` (free, no extra queries) + direct-cite bonus. Author IDF via `log(N/author.works_count)` from batched author lookups (50 IDs/call), position weights from `author_position`. Semantic: reconstruct abstract from `abstract_inverted_index`, embed locally (SPECTER2 / all-MiniLM via sentence-transformers, free) or OpenAI embeddings API, cosine → percentile-rank.
- **Status:** 💡 idea

### Paper quality score
- **What:** Score a paper's quality from realized prestige (citations) + predicted quality (author/institution prior), blended by paper age — new papers have no citation record, so the author prior carries them.
- **Blend:** `Q = w(age)·structural + (1−w(age))·author_prior`, w ramps ~0.2 at age 1 → ~0.9 at age 5.
- **Structural:** percentile within field×year (or `log(1+cites) − log(1+field-year-mean)`) to kill field/age confounds; **PageRank on citation graph** (Eigenfactor-style) so cites from important papers count more; exclude self-citations; treat review papers as a separate node type.
- **Author prior:** citations **per paper per year, field-normalized** — productivity (# papers/yr) is the *denominator*, not a quality signal; salami-slicing (high productivity, low cites/paper) gets a negative weight. Compute from prior papers only (no label leakage); aggregate as top-2 or mean over authors, never sum (50 authors ≠ 50× prior).
- **Institution:** data-driven — mean author-prior of that institution's papers in-corpus, better than QS/THE rankings; use only as fallback for no-track-record authors.
- **Why:** raw citation count is field/age/gameable-confounded; separating realized vs predicted quality handles the new-paper cold-start.
- **API-lean version** (OpenAlex + optional Semantic Scholar): structural = percentile of `log(1+cited_by_count)` within topic×year **in-corpus** (no external baseline table); if S2 is added, use its precomputed `influentialCitationCount` as the prestige term instead of PageRank (in-corpus PageRank is noise — most refs point outside the corpus). Author prior = `cited_by_count/works_count` from batched author calls, percentilized, top-2 aggregate with position weights. Drop institution entirely (subsumed by author prior; `last_known_institution` is on the author object if ever needed). Fetch budget: ~1 query/paper + 1 per 50 authors + embeddings.
- **Status:** 💡 idea
