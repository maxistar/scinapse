"""OpenAlex enrichment: venue quality, retraction, affiliations, topics, references.

``venue_quality`` is ported verbatim from the prototype notebook (cell
``336521f7``): a *venue* heuristic (paper mills publish thousands per year),
not a verdict on any paper. It stays an internal ranking signal.
"""

from __future__ import annotations

import math

from . import warnings as W
from .discovery import GraphState
from .httpjson import ApiError
from .openalex import (OpenAlexClient, normalize_authorships, normalize_institutions,
                       normalize_topics, publication_type, referenced_works, source_of)

PREPRINT_HINTS = ("biorxiv", "medrxiv", "arxiv", "ssrn", "chemrxiv", "research square", "preprint")


def venue_quality(ppy: int | None, retracted: bool = False, h_index: int = 0,
                  stype: str = "journal", name: str = "") -> float | None:
    """Journal papers/year -> soft quality in [0,1]; None = unknown venue.

    - retracted -> 0.0
    - preprint servers / repositories -> None (not peer-review-graded venues)
    - flagship weeklies (h-index >= 900) also publish thousands per year -> floor 0.75
    - otherwise: <=200/yr -> 1.0 ... ~3,200+/yr -> ~0.2 (paper-mill territory)
    """
    if retracted:
        return 0.0
    lname = (name or "").lower()
    if "preprint" in (stype or "") or "repository" in (stype or "") or any(h in lname for h in PREPRINT_HINTS):
        return None
    if not ppy:
        return None
    l = math.log10(max(ppy, 1))
    if l <= 2.3:                                   # <=200 papers/yr
        q = 1.0
    elif l <= 3.0:                                 # 200..1,000
        q = 1.0 - 0.45 * (l - 2.3) / 0.7
    elif l <= 3.5:                                 # 1,000..~3,200
        q = 0.55 - 0.30 * (l - 3.0) / 0.5
    else:                                          # paper-mill territory
        q = max(0.10, 0.25 - 0.15 * (l - 3.5))
    if (h_index or 0) >= 900:
        q = max(q, 0.75)
    return q


def enrich_openalex(state: GraphState, oa: OpenAlexClient) -> None:
    """DOI -> work (retraction, affiliations, topics, references) -> source stats."""
    src_stats: dict[str, dict | None] = {}
    matched = 0
    for rec in state.papers.values():
        if not rec.doi:
            continue
        try:
            work = oa.get_work(rec.doi)
        except ApiError as e:
            state.warnings.add(W.S2_RATE_LIMITED, message=f"openalex work {rec.doi}: {e}")
            print(f"    ! openalex {rec.doi}: {e}", flush=True)
            continue
        if work is None:
            state.warnings.add(W.OPENALEX_UNMATCHED, node_id=rec.s2_id)
            continue
        matched += 1
        rec.oa_work_url = work.get("id")
        rec.authorships = normalize_authorships(work)
        rec.institutions = normalize_institutions(work)
        rec.topics = normalize_topics(work)
        rec.refs = referenced_works(work)
        rec.is_retracted = bool(work.get("is_retracted"))
        rec.pub_type = publication_type(work, None)
        src = source_of(work)
        if src and (src.get("id") or "").rsplit("/", 1)[-1]:
            rec.source_id = src["id"].rsplit("/", 1)[-1]
            rec.source_name = src.get("display_name") or rec.venue or None
            src_stats.setdefault(rec.source_id, None)
    for sid in list(src_stats):
        try:
            s = oa.get_source(sid)
        except ApiError as e:
            print(f"    ! openalex source {sid}: {e}", flush=True)
            continue
        if s is None:
            continue
        cby = sorted(s.get("counts_by_year") or [], key=lambda c: -c.get("year", 0))
        ppy = next((c["works_count"] for c in cby if c.get("year") == 2025), None)  # last full year
        if ppy is None and cby:
            ppy = cby[0].get("works_count")
        src_stats[sid] = {
            "name": s.get("display_name"),
            "ppy": ppy,
            "h": (s.get("summary_stats") or {}).get("h_index") or 0,
            "type": s.get("type") or "journal",
            "is_preprint_repo": bool(s.get("is_preprint_repository")),
            "is_in_doaj": bool(s.get("is_in_doaj")),
        }
    for rec in state.papers.values():
        info = src_stats.get(rec.source_id)
        if rec.pub_type == "unknown" and rec.s2_pub_types:
            rec.pub_type = publication_type(None, rec.s2_pub_types)  # S2-only fallback
        if info:
            rec.ppy = info["ppy"]
            rec.source_name = (info["name"] or rec.source_name or rec.venue) or None
            rec.h_index = info["h"]
            rec.source_type = info["type"]
            rec.is_preprint_repo = info["is_preprint_repo"]
            rec.is_in_doaj = info["is_in_doaj"]
        rec.venue_quality = venue_quality(
            rec.ppy, rec.is_retracted,
            h_index=rec.h_index, stype=rec.source_type, name=rec.source_name or "",
        )
    print(f"    matched {matched} DOIs on OpenAlex; {sum(1 for v in src_stats.values() if v)} distinct journals",
          flush=True)
    n_unk = sum(1 for r in state.papers.values() if r.venue_quality is None)
    if n_unk:
        print(f"      {n_unk} papers without venue stats", flush=True)
