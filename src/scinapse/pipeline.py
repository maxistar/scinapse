"""Pipeline orchestration: seeds in -> sample_response.json-shaped document out."""

from __future__ import annotations

import time

from . import warnings as W  # noqa: F401  (re-exported for convenience)
from .assess import assess_all, make_client
from .config import BuildConfig
from .discovery import GraphState, add_top_entry, expand_layers, fetch_seeds, finalize
from .edges import build_citation_overlap_edges, build_shared_author_edges, build_similarity_edges
from .enrich import enrich_openalex
from .httpjson import Http
from .openalex import OpenAlexClient
from .s2 import S2Client
from .serialize import build_document
from .similarity import build_similarity


def run(cfg: BuildConfig, *, tf_client=None, no_llm: bool = False) -> dict:
    """Full build around the seed set (cached API calls make reruns cheap)."""
    t0 = time.time()
    cfg = cfg.with_env()
    http = Http(cfg.cache_dir, cfg.mailto)
    s2 = S2Client(http, cfg.s2_min_interval)
    oa = OpenAlexClient(http, cfg.oa_min_interval, cfg.mailto)
    state = GraphState(cfg=cfg)

    if tf_client is None and not no_llm:
        tf_client = make_client()

    print(f"1) seeds ({len(cfg.normalized_seeds)})", flush=True)
    fetch_seeds(state, s2)
    print("2) forward-citation layers", flush=True)
    expand_layers(state, s2)
    print("3) top entry: latest by author / by topic", flush=True)
    add_top_entry(state, s2)
    print("4) OpenAlex enrichment (single-record calls)", flush=True)
    enrich_openalex(state, oa)
    print("5) similarity (title+abstract)", flush=True)
    embed_client = tf_client if cfg.embed_model else None
    sim = build_similarity(state, embed_client, cfg.embed_model)
    print("6) edges: citation_overlap / shared_author / similar_to", flush=True)
    drafts = (build_citation_overlap_edges(state)
              + build_shared_author_edges(state)
              + build_similarity_edges(state, sim))
    print(f"    citation_overlap edges: {sum(1 for d in drafts if d.type == 'citation_overlap')}",
          flush=True)
    print("7) internal composite scores + evidence lines", flush=True)
    finalize(state, drafts)
    print("8) Token Factory assessment", flush=True)
    assess_all(state, tf_client, http)
    print("9) serialize", flush=True)
    doc = build_document(state, drafts)
    print(f"   -> {len(doc['nodes'])} nodes / {len(doc['edges'])} edges "
          f"in {time.time() - t0:.0f}s", flush=True)
    return doc
