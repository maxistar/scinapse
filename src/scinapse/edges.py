"""Edge builders — exactly 3 types, one [0,1] number each.

- ``citation_overlap``: value = max(direct cite ? 1.0 : 0, reference Jaccard);
  ``directed`` when a Semantic Scholar-verified direct citation exists.
- ``shared_author``: Salton ``|A∩B|/sqrt(|A|·|B|)`` over merged author keys.
- ``similar_to``: abstract cosine mapped to [0,1] via ``(v+1)/2``.

Undirected drafts keep a deterministic (sorted s2 id) endpoint order; the
serializer re-normalizes by paper number and assigns final edge ids.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

from .discovery import GraphState
from .similarity import SimResult


@dataclass
class EdgeDraft:
    src: str                       # s2 id; for direct cites: the CITING paper
    dst: str                       # s2 id; for direct cites: the CITED paper
    type: str                      # "citation_overlap" | "shared_author" | "similar_to"
    directed: bool
    strength_value: float          # final [0,1] number shown by the viz
    metric: str
    range_: tuple | None = None
    method_version: str | None = None
    components: dict | None = None
    direct_cite: bool = False

    def undirected_key(self) -> tuple[str, str]:
        return tuple(sorted((self.src, self.dst)))  # type: ignore[return-value]


def author_keys(rec) -> tuple[set[str], dict[str, str]]:
    """Merged author keys (OpenAlex id preferred, s2:{id} fallback) + display names."""
    keys: set[str] = set()
    names: dict[str, str] = {}
    for a in rec.authorships:  # OpenAlex-normalized
        if a.get("key"):
            keys.add(a["key"])
            names.setdefault(a["key"], a.get("name") or a["key"])
    for aid, name in rec.authors_s2:
        k = f"s2:{aid}"
        keys.add(k)
        names.setdefault(k, name)
    return keys, names


def build_citation_overlap_edges(state: GraphState) -> list[EdgeDraft]:
    """Verified direct cites (binary, S2) fused with bibliographic coupling (max)."""
    cfg = state.cfg
    edges: dict[tuple[str, str], EdgeDraft] = {}

    def jaccard(a, b) -> tuple[float, int, int] | None:
        if not a.refs or not b.refs:
            return None
        inter = len(a.refs & b.refs)
        union = len(a.refs | b.refs)
        return (inter / union if union else 0.0), inter, union

    # 1) direct citations — the BFS-discovered, verified pairs
    for citing, cited in sorted(state.citation_pairs):
        if citing not in state.papers or cited not in state.papers:
            continue
        jac = jaccard(state.papers[citing], state.papers[cited])
        edges[(citing, cited)] = EdgeDraft(
            src=citing, dst=cited, type="citation_overlap", directed=True,
            strength_value=1.0, metric="citation_overlap_v1", range_=(0, 1),
            method_version="citation-max-fusion-v1",
            components={
                "direct_cite": True,
                "reference_jaccard": round(jac[0], 4) if jac else None,
                "intersection_count": jac[1] if jac else None,
                "union_count": jac[2] if jac else None,
            },
            direct_cite=True,
        )

    # 2) bibliographic coupling between pairs with no direct citation either way
    with_refs = [r for r in state.papers.values() if r.refs]
    candidates = []
    for i in range(len(with_refs)):
        for j in range(i + 1, len(with_refs)):
            a, b = with_refs[i], with_refs[j]
            ka, kb = tuple(sorted((a.s2_id, b.s2_id)))
            if (ka, kb) in edges or (kb, ka) in edges:
                continue  # already emitted as a direct-cite edge (fusion handled above)
            jac = jaccard(a, b)
            if jac is None:
                continue
            value, inter, union = jac
            if inter < cfg.refs_min_intersection or value < cfg.refs_threshold:
                continue
            candidates.append((value, ka, kb, inter, union))
    candidates.sort(reverse=True)
    degree: dict[str, int] = defaultdict(int)
    for value, ka, kb, inter, union in candidates:
        if degree[ka] >= cfg.refs_top_k or degree[kb] >= cfg.refs_top_k:
            continue
        edges[(ka, kb)] = EdgeDraft(
            src=ka, dst=kb, type="citation_overlap", directed=False,
            strength_value=round(value, 4), metric="citation_overlap_v1", range_=(0, 1),
            method_version="citation-max-fusion-v1",
            components={"direct_cite": False, "reference_jaccard": round(value, 4),
                        "intersection_count": inter, "union_count": union},
        )
        degree[ka] += 1
        degree[kb] += 1
    return list(edges.values())


def build_shared_author_edges(state: GraphState) -> list[EdgeDraft]:
    """Salton author overlap; only when touching a seed or latest-entry node
    (that is the relevance question), capped per node (ported clutter control)."""
    keys_by_pid: dict[str, set[str]] = {}
    name_by_key: dict[str, str] = {}
    for pid, rec in state.papers.items():
        keys, names = author_keys(rec)
        keys_by_pid[pid] = keys
        for k, n in names.items():
            name_by_key.setdefault(k, n)

    shared: dict[tuple[str, str], list[str]] = defaultdict(list)
    pids = list(state.papers)
    for i in range(len(pids)):
        for j in range(i + 1, len(pids)):
            common = keys_by_pid[pids[i]] & keys_by_pid[pids[j]]
            if common:
                ka, kb = sorted((pids[i], pids[j]))
                shared[(ka, kb)].extend(sorted(common))

    ranked = []
    for (ka, kb), common in shared.items():
        ra, rb = state.papers[ka], state.papers[kb]
        if not (ra.is_seed or rb.is_seed or ra.entry or rb.entry):
            continue
        denom = math.sqrt(len(keys_by_pid[ka]) * len(keys_by_pid[kb]))
        salton = len(common) / denom if denom else 0.0
        if salton <= 0:
            continue
        ranked.append((salton, ka, kb, sorted(set(common))))
    ranked.sort(reverse=True)
    degree: dict[str, int] = defaultdict(int)
    out = []
    for salton, ka, kb, common in ranked:
        if degree[ka] >= state.cfg.author_top_k or degree[kb] >= state.cfg.author_top_k:
            continue
        out.append(EdgeDraft(
            src=ka, dst=kb, type="shared_author", directed=False,
            strength_value=round(salton, 4), metric="author_overlap_salton", range_=(0, 1),
            method_version="author-salton-v1",
            components={"shared_author_names": [name_by_key.get(k, k) for k in common],
                        "shared_authors_count": len(common),
                        "author_counts": [len(keys_by_pid[ka]), len(keys_by_pid[kb])]},
        ))
        degree[ka] += 1
        degree[kb] += 1
    print(f"    shared_author edges: {len(out)}", flush=True)
    return out


def build_similarity_edges(state: GraphState, sim: SimResult) -> list[EdgeDraft]:
    """Top-k cosine neighbours above the threshold, mapped to [0,1] via (v+1)/2."""
    cfg = state.cfg
    ids = sim.ids
    seen: set[tuple[str, str]] = set()
    out = []
    for i, pid in enumerate(ids):
        rec = state.papers[pid]
        added = 0
        neighbours = sorted((k for k in range(len(ids)) if k != i), key=lambda k: -sim.matrix[i][k])
        for k in neighbours:
            if added >= cfg.sim_top_k or sim.matrix[i][k] < sim.threshold:
                break
            other = ids[k]
            if rec.is_seed and state.papers[other].is_seed:
                continue  # seed-seed similarity edges carry no discovery signal
            key = tuple(sorted((pid, other)))
            if key in seen:
                continue
            seen.add(key)
            raw = float(sim.matrix[i][k])
            out.append(EdgeDraft(
                src=key[0], dst=key[1], type="similar_to", directed=False,
                strength_value=round((raw + 1) / 2, 4), metric="abstract_cosine_similarity",
                range_=(0, 1), method_version=sim.method_version + "+map01",
                components={"raw_cosine": round(raw, 4)},
            ))
            added += 1
    print(f"    similar_to edges: {len(out)}", flush=True)
    return out
