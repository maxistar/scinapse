"""Paper discovery: seed resolution, forward-citation BFS, latest-paper entry.

Ported from the prototype notebook (cells ``1977393f`` / ``e36d5abe`` /
``finalize`` in ``62dc2198``). Differences from the notebook:

- the paper store is a ``GraphState`` of ``PaperRec`` dataclasses;
- citation links found by the BFS are recorded as **verified** pairs on the
  state (they become ``citation_overlap`` edges later — never guessed);
- the layer pools used by the notebook's ``more()`` explorer are dropped
  (out of scope for the generator v1);
- ``finalize`` reads the drafted edges instead of a global EDGES list, and its
  composite score stays internal (node ordering + LLM prompt context).
"""

from __future__ import annotations

import math
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .config import BuildConfig
from .s2 import S2Client, abstract_text
from .httpjson import ApiError
from . import warnings as W


def short_title(t: str | None, n: int = 34) -> str:
    t = (t or "").strip()
    return t if len(t) <= n else t[: n - 1] + "…"


def _recency(y: int | None) -> float:
    return 1.0 if (y or 0) >= 2025 else 0.7 if (y or 0) >= 2023 else 0.4


@dataclass
class PaperRec:
    s2_id: str
    title: str
    year: int | None
    venue: str
    citation_count: int
    abstract: str
    abstract_provenance: str
    authors_s2: list[tuple[str, str]]  # (s2 authorId, display name)
    doi: str | None
    pmid: str | None
    pmcid: str | None
    is_seed: bool = False
    layer: int | None = None
    entry: str | None = None  # "author" | "topic" | "web" for latest papers

    # OpenAlex enrichment (filled by enrich.py)
    oa_work_url: str | None = None
    authorships: list[dict] = field(default_factory=list)
    institutions: list[dict] = field(default_factory=list)  # [{key, name, ror}]
    topics: list[str] = field(default_factory=list)
    s2_fields: list[str] = field(default_factory=list)
    refs: set[str] = field(default_factory=set)
    is_retracted: bool = False
    pub_type: str = "unknown"
    s2_pub_types: list[str] = field(default_factory=list)
    source_id: str | None = None
    source_name: str | None = None
    ppy: int | None = None
    h_index: int = 0
    source_type: str = "journal"
    is_preprint_repo: bool = False
    is_in_doaj: bool = False
    venue_quality: float | None = None

    # computed
    sem: float | None = None  # best seed similarity (internal ordering signal)
    composite: int | None = None
    evidence_lines: list[str] = field(default_factory=list)
    llm: dict | None = None  # filled by assess.py


@dataclass
class GraphState:
    cfg: BuildConfig
    papers: dict[str, PaperRec] = field(default_factory=dict)  # insertion-ordered
    citation_pairs: set[tuple[str, str]] = field(default_factory=set)  # (citing, cited), S2-verified
    warnings: W.WarningCollector = field(default_factory=W.WarningCollector)

    def seed_ids(self) -> set[str]:
        return {p for p, r in self.papers.items() if r.is_seed}


def add_paper(state: GraphState, p: dict, *, layer: int | None = None,
              is_seed: bool = False, entry: str | None = None) -> PaperRec | None:
    """Idempotently register a Semantic Scholar paper record."""
    pid = p.get("paperId")
    if not pid or not (p.get("title") or "").strip():
        return None
    abstract, provenance = abstract_text(p)
    ext = p.get("externalIds") or {}
    existing = state.papers.get(pid)
    if existing is None:
        existing = PaperRec(
            s2_id=pid,
            title=p["title"].strip(),
            year=p.get("year"),
            venue=p.get("venue") or "",
            citation_count=p.get("citationCount") or 0,
            abstract=abstract or "",
            abstract_provenance=provenance,
            authors_s2=[(a["authorId"], a["name"]) for a in (p.get("authors") or []) if a.get("authorId")],
            s2_pub_types=list(p.get("publicationTypes") or []),
            s2_fields=list(p.get("fieldsOfStudy") or []),
            doi=ext.get("DOI"),
            pmid=ext.get("PubMed"),
            pmcid=ext.get("PubMedCentral"),
        )
        state.papers[pid] = existing
    if is_seed:
        existing.is_seed = True
    if layer is not None and (existing.layer is None or layer < existing.layer):
        existing.layer = layer
    if entry and not existing.entry:
        existing.entry = entry
    return existing


def seed_author_ids(state: GraphState) -> set[str]:
    ids: set[str] = set()
    for r in state.papers.values():
        if r.is_seed:
            ids.update(a[0] for a in r.authors_s2)
    return ids


def fetch_seeds(state: GraphState, s2: S2Client) -> None:
    for doi in state.cfg.normalized_seeds:
        try:
            p = s2.fetch_paper_by_doi(doi)
        except ApiError as e:
            state.warnings.add(W.SEED_RESOLUTION_FAILED, message=f"Seed {doi}: {e}")
            print(f"    ! seed {doi} failed: {e}", flush=True)
            continue
        rec = add_paper(state, p, layer=0, is_seed=True)
        if rec:
            print(f"    L0 {rec.year} cites={rec.citation_count:>5} "
                  f"abs={'y' if rec.abstract else 'n'}  {short_title(rec.title, 66)}", flush=True)
    if not state.seed_ids():
        raise RuntimeError("no seed DOI could be resolved on Semantic Scholar")


def expand_layers(state: GraphState, s2: S2Client,
                  n_layers: int | None = None, top_k: int | None = None) -> None:
    """Forward-citation BFS: layer k cites layer k-1; newest work drifts upward.

    Semantic Scholar lists citers newest-first, so layer 1 fetches two windows
    per seed (recent frontier + older, established followers); deeper layers
    fetch only the recent window (ported recency weighting).
    """
    cfg = state.cfg
    n_layers = n_layers if n_layers is not None else cfg.layers
    top_k = top_k if top_k is not None else cfg.top_k_per_layer
    parents = sorted(state.seed_ids())
    s_auth = seed_author_ids(state)
    for layer in range(1, n_layers + 1):
        rec_w = {1: 0.3, 2: 0.6, 3: 1.0}.get(layer, 1.0)
        windows = [(0, 60)] if layer > 1 else [(0, 100), ("deep", 100)]
        hits: dict[str, list[str]] = defaultdict(list)
        metas: dict[str, dict] = {}
        for pid in parents:
            for offset, limit in windows:
                if offset == "deep":
                    off = max(150, min(1500, state.papers[pid].citation_count // 3))
                else:
                    off = offset
                try:
                    r = s2.fetch_citations(pid, offset=off or None, limit=limit)
                except ApiError as e:
                    state.warnings.add(W.S2_RATE_LIMITED, message=f"citations for {pid[:8]}: {e}")
                    print(f"    ! citations for {pid[:8]} failed: {e}", flush=True)
                    continue
                for row in r.get("data") or []:
                    c = row.get("citingPaper") or {}
                    cid = c.get("paperId")
                    if not cid or not (c.get("title") or "").strip():
                        continue
                    hits[cid].append(pid)
                    if cid not in state.papers:
                        metas[cid] = c
        fresh = []
        for cid, plist in hits.items():
            if cid in state.papers:
                continue
            m = metas[cid]
            y = m.get("year") or 0
            a_ids = {x["authorId"] for x in (m.get("authors") or []) if x.get("authorId")}
            score = (
                2.0 * len(plist)
                + rec_w * (1.0 if y >= 2025 else 0.6 if y >= 2023 else 0.3 if y >= 2020 else 0.0)
                + 0.5 * math.log10(1 + (m.get("citationCount") or 0)) / 3.0
                + 0.8 * float(bool(a_ids & s_auth))
            )
            fresh.append((score, cid, plist))
        fresh.sort(reverse=True)
        # year-diversity quota: at most top_k//3 picks per publication year,
        # then fill any leftover slots by raw score (ported)
        kept, kept_ids, year_count = [], set(), Counter()
        cap = max(3, top_k // 3)
        for s, cid, plist in fresh:
            if len(kept) >= top_k:
                break
            y = metas[cid].get("year") or 0
            if year_count[y] >= cap:
                continue
            kept.append((s, cid, plist))
            kept_ids.add(cid)
            year_count[y] += 1
        for s, cid, plist in fresh:
            if len(kept) >= top_k:
                break
            if cid not in kept_ids:
                kept.append((s, cid, plist))
                kept_ids.add(cid)
        for _, cid, _ in kept:
            add_paper(state, metas[cid], layer=layer)
        # record verified citation pairs for every discovered node present in
        # the store (kept this round or added by earlier layers)
        for cid, plist in hits.items():
            if cid in state.papers:
                for parent in plist:
                    state.citation_pairs.add((cid, parent))
        if not kept:
            print(f"    layer {layer}: nothing new — stopping", flush=True)
            break
        ys = sorted(state.papers[cid].year or 0 for _, cid, _ in kept)
        print(f"    layer {layer}: {len(hits)} candidates citing {len(parents)} parents "
              f"-> kept {len(kept)} (years {ys[0]}..{ys[-1]})", flush=True)
        parents = sorted(cid for _, cid, _ in kept)


def add_top_entry(state: GraphState, s2: S2Client, n: int | None = None) -> None:
    """Pin the newest relevant papers into the top layer (by author / topic).

    These papers are often too new to have citations — they anchor the
    'latest' frontier (ported from the notebook).
    """
    cfg = state.cfg
    n = n if n is not None else cfg.top_entry_n
    pool: list[tuple[str, dict]] = []
    seen: set[str] = set(state.papers)
    counts = Counter(a[0] for r in state.papers.values() if r.is_seed for a in r.authors_s2)
    anchors = [aid for aid, c in counts.most_common() if c >= 2][:3]
    if not anchors:
        anchors = [r.authors_s2[0][0] for r in state.papers.values() if r.is_seed and r.authors_s2][:3]
    for aid in anchors:
        try:
            papers = s2.fetch_author_papers(aid, 25)
        except ApiError as e:
            state.warnings.add(W.S2_RATE_LIMITED, message=f"author feed {aid}: {e}")
            print(f"    ! author feed {aid}: {e}", flush=True)
            continue
        for p in papers:
            pid = p.get("paperId")
            if pid and pid not in seen and (p.get("year") or 0) >= cfg.recent_min_year:
                seen.add(pid)
                pool.append(("author", p))
    try:
        results = s2.search_papers(
            state.cfg.question, year_range=f"{cfg.recent_min_year}-{time.gmtime().tm_year}", limit=25)
        for p in results:
            pid = p.get("paperId")
            if pid and pid not in seen:
                seen.add(pid)
                pool.append(("topic", p))
    except ApiError as e:
        state.warnings.add(W.TOPIC_SEARCH_UNAVAILABLE, message=str(e))
        print(f"    ! topic search: {e}", flush=True)
    pool.sort(key=lambda ep: ((ep[1].get("year") or 0), ep[1].get("citationCount") or 0), reverse=True)
    for entry, p in pool[:n]:
        rec = add_paper(state, p, layer=state.cfg.layers, entry=entry)
        if rec:
            print(f"    latest[{entry:>6}] {rec.year} cites={rec.citation_count:>3}  "
                  f"{short_title(rec.title, 62)}", flush=True)


def finalize(state: GraphState, drafts: list) -> None:
    """Internal composite relevance score + evidence lines per paper.

    This drives node ordering and gives the LLM assessor its context; the
    document's ``relevance`` block comes from the LLM rubric instead.
    """
    seed_ids = state.seed_ids()
    by_pair: dict[tuple[str, str], list] = {}
    for d in drafts:
        key = (d.src, d.dst)
        by_pair.setdefault(key, []).append(d)
        if not getattr(d, "directed", False):
            by_pair.setdefault((d.dst, d.src), []).append(d)

    def drafts_of(pid: str, etype: str | None = None) -> list:
        out = []
        for (a, b), ds in by_pair.items():
            if a == pid:
                out.extend(d for d in ds if etype is None or d.type == etype)
        return out

    for pid, rec in state.papers.items():
        if rec.is_seed:
            rec.composite = None
            rec.evidence_lines = ["seed paper — your starting collection"]
            continue
        cites_seed = [d for d in drafts_of(pid, "citation_overlap")
                      if d.direct_cite and d.src == pid and d.dst in seed_ids]
        cites_other = [d for d in drafts_of(pid, "citation_overlap")
                       if d.direct_cite and d.src == pid and d.dst not in seed_ids]
        auth_e = drafts_of(pid, "shared_author")
        sem_e = drafts_of(pid, "similar_to")
        rec.composite = round(100 * (
            0.45 * min((rec.sem or 0) / 0.5, 1.0)
            + 0.25 * min(len(cites_seed) / 2.0, 1.0)
            + 0.15 * min(len(cites_other) / 3.0, 1.0)
            + 0.10 * _recency(rec.year)
            + 0.05 * min(len(auth_e) / 2.0, 1.0)
        ))
        ev = []
        if cites_seed:
            names = "; ".join(short_title(state.papers[d.dst].title, 40) for d in cites_seed[:3])
            ev.append(f"cites {len(cites_seed)} seed paper(s): {names}")
        if cites_other:
            ev.append(f"cites {len(cites_other)} discovered paper(s) on paths to the seeds")
        if sem_e:
            best = max(sem_e, key=lambda d: d.strength_value or 0.0)
            other = best.dst if best.src == pid else best.src
            raw = (best.components or {}).get("raw_cosine")
            ev.append(f"abstract similarity {raw:.2f} with {short_title(state.papers[other].title, 40)}")
        if auth_e:
            n_shared = sum((d.components or {}).get("shared_authors_count", 0) for d in auth_e[:3])
            ev.append(f"shares author(s) with {len(auth_e)} paper(s) in the graph"
                      + (f" ({n_shared} shared author links)" if n_shared else ""))
        if rec.entry:
            ev.append(f"latest work (entered by {rec.entry}) — no citation links yet")
        rec.evidence_lines = ev or ["no explicit connection extracted"]
