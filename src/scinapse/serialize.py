"""Document assembly: GraphState + EdgeDrafts -> the sample_response.json shape.

Exact key order per the sample; ids are sequential and deterministic given the
same API responses (node order: seeds in input order, then layer asc, then
internal composite desc, then s2 id).
"""

from __future__ import annotations

from . import warnings as W
from .config import BuildConfig, exploration_id
from .discovery import GraphState, PaperRec, short_title
from .edges import EdgeDraft
from .ids import IdAllocator
from .static_blocks import ASSESSMENT_POLICY, GRAPH_VIEW, SCHEMA_VERSION
from .textutil import first_sentence

EDGE_SUFFIX = {"citation_overlap": "citation_overlap", "shared_author": "shared_author",
               "similar_to": "similarity"}
EDGE_ORDER = {"citation_overlap": 0, "shared_author": 1, "similar_to": 2}

WEIGHTS = ASSESSMENT_POLICY["relevance_scoring"]["weights"]
THRESHOLDS = ASSESSMENT_POLICY["relevance_scoring"]["assessment_thresholds"]


def relevance_bucket(score: float | None) -> str:
    if score is None:
        return "uncertain"
    for name in ("highly_relevant", "potentially_relevant", "indirectly_relevant", "not_relevant"):
        lo, hi = THRESHOLDS[name]
        if lo <= score < hi or (score >= 1.0 and name == "highly_relevant"):
            return name
    return "uncertain"


def paper_url(rec: PaperRec) -> str:
    if rec.doi:
        return f"https://doi.org/{rec.doi}"
    return f"https://www.semanticscholar.org/paper/{rec.s2_id}"


def _ordered_s2_ids(state: GraphState) -> list[str]:
    seeds = [p for p, r in state.papers.items() if r.is_seed]
    rest = [p for p, r in state.papers.items() if not r.is_seed]
    rest.sort(key=lambda p: (state.papers[p].layer if state.papers[p].layer is not None else 99,
                             -(state.papers[p].composite or 0), p))
    return seeds + rest


def _node_authors(rec: PaperRec, alloc: IdAllocator) -> list[dict]:
    if rec.authorships:
        entries = [(a["key"], a.get("name") or a["key"], a.get("orcid"), a.get("inst_keys") or [])
                   for a in rec.authorships]
    else:
        entries = [(f"s2:{aid}", name, None, []) for aid, name in rec.authors_s2]
    out = []
    for key, name, orcid, insts in entries:
        out.append({"id": alloc.author(key), "name": name, "orcid": orcid,
                    "affiliation_ids": [alloc.institution(i) for i in insts]})
    return out


def _node_institutions(rec: PaperRec, alloc: IdAllocator) -> list[dict]:
    return [{"id": alloc.institution(i["key"]), "name": i["name"] or i["key"],
             "ror": i.get("ror"), "verification_status": "matched_openalex"}
            for i in rec.institutions]


def _relevance_block(rec: PaperRec, text_ev: str, llm: dict | None) -> dict:
    dims = {k: None for k in WEIGHTS}
    provenance = "template_v1"
    if llm:
        provenance = "llm_abstract_rubric_v1"
        for k in dims:
            v = (llm.get("dimensions") or {}).get(k)
            dims[k] = None if v is None else round(min(max(float(v), 0.0), 1.0), 2)
    if all(v is not None for v in dims.values()):
        score = round(sum(WEIGHTS[k] * dims[k] for k in WEIGHTS), 2)
        assessment, status = relevance_bucket(score), "ready"
    else:
        score, assessment, status = None, "uncertain", "insufficient_evidence"
    return {
        "status": status,
        "assessment": assessment,
        "reason": (llm or {}).get("reason") or " | ".join(rec.evidence_lines),
        "supporting_evidence_ids": [text_ev],
        "uncertainties": (llm or {}).get("uncertainties") or [],
        "score": score,
        "scale": {"min": 0, "max": 1},
        "dimensions": dims,
        "scoring": {"method": "weighted_rubric", "version": "relevance_v1",
                    "weights": dict(WEIGHTS), "provenance": provenance},
    }


def _research_assessment_block(rec: PaperRec, llm: dict | None) -> dict:
    llm_ra = (llm or {}).get("research_assessment") or {}

    def dim(name, fallback_reason):
        d = llm_ra.get(name) or {}
        assessment = d.get("assessment") or "not_assessed"
        if assessment not in ("not_assessed", "unknown", "partial_evidence"):
            assessment = "not_assessed"
        return {"assessment": assessment,
                "reason": d.get("reason") or fallback_reason,
                "evidence_ids": []}

    if rec.institutions:
        author_ctx = {"assessment": "partially_verified",
                      "reason": "Affiliations matched to OpenAlex institution records; "
                                "author identities not independently verified.",
                      "evidence_ids": []}
    else:
        author_ctx = {"assessment": "unknown",
                      "reason": "Affiliations were not matched to any institution registry.",
                      "evidence_ids": []}
    return {
        "status": "partial" if rec.abstract else "insufficient_evidence",
        "overall_score": None,
        "summary": (llm or {}).get("summary")
                   or ("Assessed from the abstract only; full-text quality has not been inspected."
                       if rec.abstract else
                       "No abstract available; research quality cannot be assessed."),
        "dimensions": {
            "methodological_rigor": dim(
                "methodological_rigor",
                "Full methods, controls, and analysis were not inspected."),
            "evidence_strength": dim(
                "evidence_strength",
                "Results and statistical analyses were not inspected."),
            "transparency": dim(
                "transparency",
                "Data and code availability have not been checked."),
            "author_institution_context": author_ctx,
            "independent_validation": {
                "assessment": "not_assessed",
                "reason": "Independent validation has not been investigated.",
                "evidence_ids": [],
            },
        },
        "evaluated_from": ["abstract" if rec.abstract else "title"],
        "limitations": ["Quality dimensions are assessed from the abstract only; full methods, "
                        "results, and data availability were not inspected.",
                        "Citation connections do not establish research quality."],
        "assessment_method": "llm_abstract_v1" if llm else "template_v1",
    }


def _node_json(rec: PaperRec, alloc: IdAllocator, text_ev: str) -> dict:
    llm = rec.llm
    url = paper_url(rec)
    abstract = None
    if rec.abstract:
        abstract = {"text": rec.abstract, "source_url": url,
                    "provenance": rec.abstract_provenance}
    return {
        "id": alloc.paper(rec.s2_id),
        "title": rec.title,
        "authors": _node_authors(rec, alloc),
        "institutions": _node_institutions(rec, alloc),
        "year": rec.year,
        "journal": rec.source_name or rec.venue or "",
        "identifiers": {"doi": rec.doi, "pmid": rec.pmid, "pmcid": rec.pmcid},
        "is_seed": rec.is_seed,
        "url": url,
        "abstract_available": bool(rec.abstract),
        "abstract": abstract,
        "topics": rec.topics or rec.s2_fields,
        "methods": (llm or {}).get("methods") or [],
        "publication_status": {
            "type": rec.pub_type,
            "peer_review": ("not_peer_reviewed"
                            if (rec.is_preprint_repo or rec.pub_type == "preprint")
                            else "peer_reviewed" if rec.is_in_doaj else "unknown"),
            "correction_status": "not_checked",
            "retraction_status": "retracted" if rec.is_retracted else "not_retracted",
        },
        "relevance": _relevance_block(rec, text_ev, llm),
        "research_assessment": _research_assessment_block(rec, llm),
        "review": {"saved": False, "decision": None, "note": None},
    }


def _edge_json(d: EdgeDraft, state: GraphState, alloc: IdAllocator,
               text_evs: dict[str, str], ref_evs: dict[str, str], author_evs: dict[str, str],
               w2s2: dict[str, str]) -> dict:
    src, dst = d.src, d.dst
    num = lambda pid: int(alloc.paper(pid).split("_")[1])  # noqa: E731
    if not d.directed and num(dst) < num(src):
        src, dst = dst, src
    a, b = state.papers[src], state.papers[dst]
    ta, tb = short_title(a.title, 40), short_title(b.title, 40)
    eid = f"edge_{num(src):03d}_{num(dst):03d}_{EDGE_SUFFIX[d.type]}"
    comps = d.components or {}

    reasoning: dict = {}
    strength_explanation = ""
    confidence = {"level": "medium", "reason": ""}
    verification = {"status": "computed", "provider": "scinapse_local",
                    "source_url": None, "evidence_ids": []}

    if d.type == "citation_overlap":
        inter = comps.get("intersection_count")
        union = comps.get("union_count")
        in_corpus = sorted({alloc.paper(w2s2[w]) for w in (a.refs & b.refs) if w in w2s2})
        if d.direct_cite:
            reasoning["summary"] = (f"'{ta}' includes '{tb}' in its reference list "
                                    f"(verified Semantic Scholar citation).")
            if inter:
                reasoning["summary"] += f" Their reference lists also share {inter} of {union} references."
            reasoning["limitations"] = ["Citation context was not inspected; influence or "
                                        "agreement cannot be inferred."]
            strength_explanation = ("Direct citation verified via Semantic Scholar; reference-list "
                                    "Jaccard is recorded in components.")
            confidence = {"level": "high",
                          "reason": "Citation link verified via Semantic Scholar citation records."}
            verification = {"status": "verified", "provider": "semantic_scholar",
                            "source_url": a.oa_work_url or paper_url(a), "evidence_ids": []}
        else:
            pct = round(100 * d.strength_value)
            reasoning["summary"] = (f"Reference lists share {inter} of {union} references "
                                    f"({pct}% Jaccard overlap).")
            reasoning["limitations"] = ["Overlap is computed from OpenAlex reference lists, which may "
                                        "be incomplete; shared references do not imply a direct relationship."]
            strength_explanation = (f"Shared references divided by the union of both reference "
                                    f"lists: {inter} / {union}.")
            confidence = {"level": "medium",
                          "reason": "Computed from OpenAlex reference lists; not independently evaluated."}
            verification = {"status": "computed", "provider": "scinapse_local",
                            "source_url": a.oa_work_url, "evidence_ids": []}
        if in_corpus:
            reasoning["shared_reference_ids"] = in_corpus
        reasoning["supporting_evidence_ids"] = [ev for ev in (ref_evs.get(src), ref_evs.get(dst)) if ev]
        verification["evidence_ids"] = list(reasoning["supporting_evidence_ids"])
    elif d.type == "shared_author":
        names = comps.get("shared_author_names") or []
        n = comps.get("shared_authors_count") or len(names)
        reasoning["summary"] = f"Shares {n} author(s): {', '.join(names)}."
        reasoning["supporting_evidence_ids"] = [ev for ev in (author_evs.get(src), author_evs.get(dst)) if ev]
        reasoning["limitations"] = ["A shared author does not establish topical similarity "
                                    "or agreement between the papers."]
        strength_explanation = ("Salton author overlap: shared authors divided by "
                                "sqrt(author_count_a * author_count_b).")
        confidence = {"level": "medium",
                      "reason": "Computed from OpenAlex and Semantic Scholar author records; "
                                "author disambiguation is approximate."}
        verification["evidence_ids"] = list(reasoning["supporting_evidence_ids"])
    else:  # similar_to
        raw = comps.get("raw_cosine")
        reasoning["summary"] = f"Title/abstract similarity (cosine {raw:.2f}) between '{ta}' and '{tb}'."
        shared_topics = sorted(set(a.topics or a.s2_fields) & set(b.topics or b.s2_fields))
        shared_methods = sorted(set((a.llm or {}).get("methods") or [])
                                & set((b.llm or {}).get("methods") or []))
        if shared_topics:
            reasoning["shared_topics"] = shared_topics
        if shared_methods:
            reasoning["shared_methods"] = shared_methods
        reasoning["supporting_evidence_ids"] = [ev for ev in (text_evs.get(src), text_evs.get(dst)) if ev]
        reasoning["limitations"] = ["Abstract similarity does not establish equivalent findings "
                                    "or scientific agreement."]
        strength_explanation = (f"Cosine similarity of title+abstract (raw {raw:.2f}, "
                                f"{d.method_version}), mapped to [0,1] via (v+1)/2.")
        confidence = {"level": "medium",
                      "reason": "Computed similarity; not independently evaluated."}
        verification["evidence_ids"] = list(reasoning["supporting_evidence_ids"])

    # sample key order: summary, [shared_topics, shared_methods | shared_reference_ids],
    # supporting_evidence_ids, limitations — rebuild in order
    ordered_reasoning = {"summary": reasoning["summary"]}
    for k in ("shared_topics", "shared_methods", "shared_reference_ids"):
        if k in reasoning:
            ordered_reasoning[k] = reasoning[k]
    ordered_reasoning["supporting_evidence_ids"] = reasoning["supporting_evidence_ids"]
    ordered_reasoning["limitations"] = reasoning["limitations"]

    strength = {"status": "computed", "value": d.strength_value, "metric": d.metric,
                "range": list(d.range_) if d.range_ else [0, 1],
                "method_version": d.method_version}
    if d.components:
        strength["components"] = {k: v for k, v in d.components.items()}
    strength["explanation"] = strength_explanation

    return {
        "id": eid,
        "source": alloc.paper(src),
        "target": alloc.paper(dst),
        "type": d.type,
        "directed": d.directed,
        "reasoning": ordered_reasoning,
        "strength": strength,
        "confidence": confidence,
        "verification": verification,
        "display_score": {"value": d.strength_value, "method": "relationship_priority_v1",
                          "provenance": "scinapse_local"},
    }


def build_document(state: GraphState, drafts: list[EdgeDraft]) -> dict:
    cfg: BuildConfig = state.cfg
    alloc = IdAllocator()
    ordered = _ordered_s2_ids(state)

    # OpenAlex W-id -> s2-id crosswalk (for in-corpus reference intersections)
    w2s2 = {}
    for rec in state.papers.values():
        if rec.oa_work_url:
            w2s2[rec.oa_work_url.rsplit("/", 1)[-1]] = rec.s2_id

    # registry for institution display info
    text_evs: dict[str, str] = {}
    text_quote: dict[str, dict] = {}
    for s2_id in ordered:
        rec = state.papers[s2_id]
        ev = alloc.next_evidence()
        text_evs[s2_id] = ev
        if rec.abstract:
            quote = ((rec.llm or {}).get("quote") or "").strip() or first_sentence(rec.abstract)
            text_quote[s2_id] = {"type": "text_passage", "id": ev, "paper": s2_id,
                                 "source_field": "abstract", "quote": quote,
                                 "provenance": rec.abstract_provenance}
        else:
            state.warnings.add(W.ABSTRACT_UNAVAILABLE, node_id=s2_id)
            text_quote[s2_id] = {"type": "text_passage", "id": ev, "paper": s2_id,
                                 "source_field": "title", "quote": rec.title,
                                 "provenance": "semantic_scholar"}

    nodes = [_node_json(state.papers[p], alloc, text_evs[p]) for p in ordered]

    # evidence lists for edges (only nodes that need them)
    in_citation = {d.src for d in drafts if d.type == "citation_overlap"} | \
                  {d.dst for d in drafts if d.type == "citation_overlap"}
    in_author = {d.src for d in drafts if d.type == "shared_author"} | \
                {d.dst for d in drafts if d.type == "shared_author"}
    ref_evs: dict[str, str] = {}
    author_evs: dict[str, str] = {}
    extra_evidence = []
    for s2_id in ordered:
        rec = state.papers[s2_id]
        if s2_id in in_citation and rec.oa_work_url:
            ev = alloc.next_evidence()
            ref_evs[s2_id] = ev
            in_corpus = sorted(alloc.paper(w2s2[w]) for w in rec.refs if w in w2s2)
            extra_evidence.append({"id": ev, "type": "reference_list", "paper": s2_id,
                                   "referenced_paper_ids": in_corpus,
                                   "source_url": rec.oa_work_url, "provenance": "openalex"})
        if s2_id in in_author:
            ev = alloc.next_evidence()
            author_evs[s2_id] = ev
            names = ([a.get("name") for a in rec.authorships if a.get("name")]
                     or [n for _, n in rec.authors_s2])
            extra_evidence.append({"id": ev, "type": "author_list", "paper": s2_id,
                                   "author_names": names, "source_url": paper_url(rec),
                                   "provenance": "openalex" if rec.authorships else "semantic_scholar"})

    def _num(pid: str) -> int:
        return int(alloc.paper(pid).split("_")[1])

    ordered_drafts = sorted(drafts, key=lambda d: (EDGE_ORDER[d.type], _num(d.src), _num(d.dst)))
    edges = [_edge_json(d, state, alloc, text_evs, ref_evs, author_evs, w2s2)
             for d in ordered_drafts]

    evidence = []
    for s2_id in ordered:  # text passages first, in node order (sample pattern)
        q = text_quote[s2_id]
        evidence.append({
            "id": q["id"], "type": "text_passage", "paper_id": alloc.paper(s2_id),
            "source_field": q["source_field"], "quote": q["quote"],
            "source_url": paper_url(state.papers[s2_id]), "provenance": q["provenance"],
        })
    for e in extra_evidence:  # then reference/author lists, in node order
        if e["type"] == "reference_list":
            evidence.append({"id": e["id"], "type": "reference_list",
                             "paper_id": alloc.paper(e["paper"]),
                             "referenced_paper_ids": e["referenced_paper_ids"],
                             "source_url": e["source_url"], "provenance": e["provenance"]})
    for e in extra_evidence:
        if e["type"] == "author_list":
            evidence.append({"id": e["id"], "type": "author_list",
                             "paper_id": alloc.paper(e["paper"]),
                             "author_names": e["author_names"],
                             "source_url": e["source_url"], "provenance": e["provenance"]})

    state.warnings.add(W.PARTIAL_QUALITY_ASSESSMENT)
    # warnings carry s2 ids internally; the contract wants node ids (paper_NNN)
    warnings = [{"code": wd["code"],
                 "node_id": alloc.paper_of(wd["node_id"]) if wd["node_id"] else None,
                 "message": wd["message"]}
                for wd in state.warnings.to_json()]

    return {
        "schema_version": SCHEMA_VERSION,
        "exploration_id": exploration_id(cfg.seeds, cfg.question),
        "is_demo": False,
        "research_question": cfg.question,
        "assessment_policy": ASSESSMENT_POLICY,
        "nodes": nodes,
        "edges": edges,
        "evidence": evidence,
        "next_cursor": None,
        "warnings": warnings,
        "graph_view": GRAPH_VIEW,
    }
