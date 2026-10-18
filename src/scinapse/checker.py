"""Structural validation of generated documents.

Two modes:

- ``check_key_order(doc)`` — pure key-order conformance against the shapes
  observed in ``sample_response.json`` (legacy sample edge types allowed).
  Used by the self-test proving these expectations really match the sample.
- ``check(doc)`` — the generator contract: key order, enums (with documented
  extensions), id formats, cross-reference integrity, formula recomputation
  (relevance weighted rubric, display_score mirroring strength), quote
  containment, and absence of demo strings.
"""

from __future__ import annotations

import re

from .static_blocks import ASSESSMENT_POLICY
from .textutil import normalize_text

TOP = ["schema_version", "exploration_id", "is_demo", "research_question", "assessment_policy",
       "nodes", "edges", "evidence", "next_cursor", "warnings", "graph_view"]
NODE = ["id", "title", "authors", "institutions", "year", "journal", "identifiers", "is_seed",
        "url", "abstract_available", "abstract", "topics", "methods", "publication_status",
        "relevance", "research_assessment", "review"]
AUTHOR = ["id", "name", "orcid", "affiliation_ids"]
INSTITUTION = ["id", "name", "ror", "verification_status"]
IDENTIFIERS = ["doi", "pmid", "pmcid"]
ABSTRACT = ["text", "source_url", "provenance"]
PUB_STATUS = ["type", "peer_review", "correction_status", "retraction_status"]
RELEVANCE = ["status", "assessment", "reason", "supporting_evidence_ids", "uncertainties",
             "score", "scale", "dimensions", "scoring"]
SCALE = ["min", "max"]
SCORING = ["method", "version", "weights", "provenance"]
RA = ["status", "overall_score", "summary", "dimensions", "evaluated_from", "limitations",
      "assessment_method"]
RA_DIM = ["assessment", "reason", "evidence_ids"]
REVIEW = ["saved", "decision", "note"]
EDGE = ["id", "source", "target", "type", "directed", "reasoning", "strength", "confidence",
        "verification", "display_score"]
REASONING_ORDER = ["summary", "shared_topics", "shared_methods", "shared_reference_ids",
                   "supporting_evidence_ids", "limitations"]
STRENGTH = ["status", "value", "metric", "range", "method_version", "components", "explanation"]
CONFIDENCE = ["level", "reason"]
VERIFICATION = ["status", "provider", "source_url", "evidence_ids"]
DISPLAY = ["value", "method", "provenance"]
EV = {
    "text_passage": ["id", "type", "paper_id", "source_field", "quote", "source_url", "provenance"],
    "reference_list": ["id", "type", "paper_id", "referenced_paper_ids", "source_url", "provenance"],
    "author_list": ["id", "type", "paper_id", "author_names", "source_url", "provenance"],
}
WARNING = ["code", "node_id", "message"]

EDGE_TYPES = {"citation_overlap", "shared_author", "similar_to"}
EDGE_SUFFIX = {"citation_overlap": "citation_overlap", "shared_author": "shared_author",
               "similar_to": "similarity"}
LEGACY_EDGE_TYPES = {"cites": "cites", "shared_references": "shared_references"}  # sample only
PUB_TYPES = {"journal_article", "preprint", "review_article", "other", "unknown"}
PEER_REVIEW = {"peer_reviewed", "not_peer_reviewed", "unknown"}
RETRACTION = {"retracted", "not_retracted", "not_checked"}
CONFIDENCE_LEVELS = {"high", "medium", "not_assessed"}
VERIF_STATUS = {"verified", "computed"}
RELEVANCE_STATUS = {"ready", "insufficient_evidence"}
ASSESSMENTS = {"highly_relevant", "potentially_relevant", "indirectly_relevant",
               "not_relevant", "uncertain"}
RA_STATUS = {"partial", "insufficient_evidence"}
RA_DIM_ASSESSMENT = {"not_assessed", "unknown", "partial_evidence", "unverified",
                     "partially_verified"}
STRENGTH_STATUS = {"computed"}
EV_TYPES = set(EV)

WEIGHTS = ASSESSMENT_POLICY["relevance_scoring"]["weights"]
THRESHOLDS = ASSESSMENT_POLICY["relevance_scoring"]["assessment_thresholds"]

DEMO_STRINGS = ("fictional_demo", "example.org", "exp_demo", "demo-embedding", "Demo Author")


def _keys_in_order(obj: dict, expected: list[str], where: str, errors: list[str]) -> None:
    got = list(obj.keys())
    if got != [k for k in expected if k in got] or set(got) - set(expected):
        errors.append(f"{where}: keys {got} do not follow the expected order/set {expected}")


def _norm(s: str) -> str:
    return normalize_text(s)


def _bucket(score: float) -> str:
    for name in ("highly_relevant", "potentially_relevant", "indirectly_relevant", "not_relevant"):
        lo, hi = THRESHOLDS[name]
        if lo <= score < hi or (score >= 1.0 and name == "highly_relevant"):
            return name
    return "uncertain"


def check_key_order(doc: dict) -> list[str]:
    """Key-order conformance only (the sample itself must pass this)."""
    errors: list[str] = []
    _keys_in_order(doc, TOP, "document", errors)
    for i, n in enumerate(doc.get("nodes") or []):
        w = f"nodes[{i}]"
        _keys_in_order(n, NODE, w, errors)
        for j, a in enumerate(n.get("authors") or []):
            _keys_in_order(a, AUTHOR, f"{w}.authors[{j}]", errors)
        for j, inst in enumerate(n.get("institutions") or []):
            _keys_in_order(inst, INSTITUTION, f"{w}.institutions[{j}]", errors)
        _keys_in_order(n.get("identifiers") or {}, IDENTIFIERS, f"{w}.identifiers", errors)
        if n.get("abstract") is not None:
            _keys_in_order(n["abstract"], ABSTRACT, f"{w}.abstract", errors)
        _keys_in_order(n.get("publication_status") or {}, PUB_STATUS, f"{w}.publication_status", errors)
        rel = n.get("relevance") or {}
        _keys_in_order(rel, RELEVANCE, f"{w}.relevance", errors)
        _keys_in_order(rel.get("scale") or {}, SCALE, f"{w}.relevance.scale", errors)
        _keys_in_order(rel.get("scoring") or {}, SCORING, f"{w}.relevance.scoring", errors)
        _keys_in_order(n.get("research_assessment") or {}, RA, f"{w}.research_assessment", errors)
        for d in (n.get("research_assessment") or {}).get("dimensions", {}).values():
            _keys_in_order(d, RA_DIM, f"{w}.research_assessment.dimensions[]", errors)
        _keys_in_order(n.get("review") or {}, REVIEW, f"{w}.review", errors)
    for i, e in enumerate(doc.get("edges") or []):
        w = f"edges[{i}]"
        _keys_in_order(e, EDGE, w, errors)
        r = e.get("reasoning") or {}
        got = list(r.keys())
        allowed = [k for k in REASONING_ORDER if k in got]
        if got != allowed:
            errors.append(f"{w}.reasoning: keys {got} do not follow {REASONING_ORDER}")
        _keys_in_order(e.get("strength") or {}, STRENGTH, f"{w}.strength", errors)
        _keys_in_order(e.get("confidence") or {}, CONFIDENCE, f"{w}.confidence", errors)
        _keys_in_order(e.get("verification") or {}, VERIFICATION, f"{w}.verification", errors)
        _keys_in_order(e.get("display_score") or {}, DISPLAY, f"{w}.display_score", errors)
    for i, ev in enumerate(doc.get("evidence") or []):
        keys = EV.get(ev.get("type"))
        if keys is None:
            errors.append(f"evidence[{i}]: unknown type {ev.get('type')!r}")
            continue
        _keys_in_order(ev, keys, f"evidence[{i}]", errors)
    for i, warn in enumerate(doc.get("warnings") or []):
        _keys_in_order(warn, WARNING, f"warnings[{i}]", errors)
    return errors


def check(doc: dict) -> list[str]:
    """Full generator-contract validation (empty list = pass)."""
    errors = check_key_order(doc)  # legacy types will be flagged; generated docs have none
    nodes = doc.get("nodes") or []
    node_ids = [n.get("id") for n in nodes]
    ev_ids = [e.get("id") for e in doc.get("evidence") or []]
    inst_ids = {i.get("id") for n in nodes for i in n.get("institutions") or []}

    if doc.get("is_demo") is not False:
        errors.append("is_demo must be false for generated documents")

    # nodes ---------------------------------------------------------------
    seeds = 0
    for i, n in enumerate(nodes):
        w = f"nodes[{i}]"
        if not re.fullmatch(r"paper_\d{3}", n.get("id") or ""):
            errors.append(f"{w}: bad id {n.get('id')!r}")
        if n.get("is_seed"):
            seeds += 1
        for j, a in enumerate(n.get("authors") or []):
            if not re.fullmatch(r"author_\d{3}", a.get("id") or ""):
                errors.append(f"{w}.authors[{j}]: bad id {a.get('id')!r}")
            for aff in a.get("affiliation_ids") or []:
                if aff not in inst_ids:
                    errors.append(f"{w}.authors[{j}]: affiliation {aff} not in any institution")
        ps = n.get("publication_status") or {}
        if ps.get("type") not in PUB_TYPES:
            errors.append(f"{w}.publication_status.type: {ps.get('type')!r}")
        if ps.get("peer_review") not in PEER_REVIEW:
            errors.append(f"{w}.publication_status.peer_review: {ps.get('peer_review')!r}")
        if ps.get("retraction_status") not in RETRACTION:
            errors.append(f"{w}.publication_status.retraction_status: {ps.get('retraction_status')!r}")
        rel = n.get("relevance") or {}
        if rel.get("status") not in RELEVANCE_STATUS:
            errors.append(f"{w}.relevance.status: {rel.get('status')!r}")
        if rel.get("assessment") not in ASSESSMENTS:
            errors.append(f"{w}.relevance.assessment: {rel.get('assessment')!r}")
        dims = rel.get("dimensions") or {}
        if set(dims) != set(WEIGHTS):
            errors.append(f"{w}.relevance.dimensions: keys {sorted(dims)}")
        score = rel.get("score")
        if all(v is not None for v in dims.values()):
            expected = round(sum(WEIGHTS[k] * dims[k] for k in WEIGHTS), 2)
            if score != expected:
                errors.append(f"{w}.relevance.score {score} != weighted rubric {expected}")
            if rel.get("assessment") != _bucket(expected):
                errors.append(f"{w}.relevance.assessment {rel.get('assessment')!r} "
                              f"!= bucket {_bucket(expected)!r}")
        elif score is not None:
            errors.append(f"{w}.relevance.score must be null when a dimension is unknown")
        if (rel.get("scale") or {}) != {"min": 0, "max": 1}:
            errors.append(f"{w}.relevance.scale must be {{min: 0, max: 1}}")
        if (rel.get("scoring") or {}).get("weights") != WEIGHTS:
            errors.append(f"{w}.relevance.scoring.weights must match the assessment policy")
        ra = n.get("research_assessment") or {}
        if ra.get("status") not in RA_STATUS:
            errors.append(f"{w}.research_assessment.status: {ra.get('status')!r}")
        for dname, d in (ra.get("dimensions") or {}).items():
            if d.get("assessment") not in RA_DIM_ASSESSMENT:
                errors.append(f"{w}.research_assessment.dimensions.{dname}.assessment: "
                              f"{d.get('assessment')!r}")
    if seeds == 0:
        errors.append("document must contain at least one seed node")

    # edges ---------------------------------------------------------------
    for i, e in enumerate(doc.get("edges") or []):
        w = f"edges[{i}]"
        etype = e.get("type")
        if etype not in EDGE_TYPES:
            errors.append(f"{w}: type {etype!r} not in the 3-type contract")
            continue
        src, dst = e.get("source"), e.get("target")
        if src not in node_ids or dst not in node_ids:
            errors.append(f"{w}: endpoint not a node ({src} -> {dst})")
        if not re.fullmatch(r"edge_\d{3}_\d{3}_" + EDGE_SUFFIX[etype], e.get("id") or ""):
            errors.append(f"{w}: bad id {e.get('id')!r} for type {etype}")
        if etype != "citation_overlap" and e.get("directed") is not False:
            errors.append(f"{w}: only citation_overlap may be directed")
        s = e.get("strength") or {}
        if s.get("status") not in STRENGTH_STATUS:
            errors.append(f"{w}.strength.status: {s.get('status')!r}")
        v = s.get("value")
        if not isinstance(v, (int, float)) or not (0.0 <= v <= 1.0):
            errors.append(f"{w}.strength.value {v!r} outside [0,1]")
        ds = e.get("display_score") or {}
        if ds.get("value") != v:
            errors.append(f"{w}.display_score.value {ds.get('value')!r} != strength.value {v!r}")
        if (e.get("confidence") or {}).get("level") not in CONFIDENCE_LEVELS:
            errors.append(f"{w}.confidence.level: {(e.get('confidence') or {}).get('level')!r}")
        if (e.get("verification") or {}).get("status") not in VERIF_STATUS:
            errors.append(f"{w}.verification.status: {(e.get('verification') or {}).get('status')!r}")
        for ev in ((e.get("reasoning") or {}).get("supporting_evidence_ids") or []):
            if ev not in ev_ids:
                errors.append(f"{w}: supporting evidence {ev} not in evidence[]")
        for ev in ((e.get("verification") or {}).get("evidence_ids") or []):
            if ev not in ev_ids:
                errors.append(f"{w}: verification evidence {ev} not in evidence[]")
        for rid in ((e.get("reasoning") or {}).get("shared_reference_ids") or []):
            if rid not in node_ids:
                errors.append(f"{w}: shared_reference_id {rid} not a node")

    # warnings ------------------------------------------------------------
    for i, warn in enumerate(doc.get("warnings") or []):
        nid = warn.get("node_id")
        if nid is not None and nid not in node_ids:
            errors.append(f"warnings[{i}].node_id: {nid!r} not a node id")

    # evidence ------------------------------------------------------------
    abstracts = {n["id"]: (n.get("abstract") or {}).get("text") for n in nodes}
    titles = {n["id"]: n.get("title") for n in nodes}
    for i, ev in enumerate(doc.get("evidence") or []):
        w = f"evidence[{i}]"
        if ev.get("type") not in EV_TYPES:
            errors.append(f"{w}: unknown type {ev.get('type')!r}")
        if not re.fullmatch(r"ev_\d{3}", ev.get("id") or ""):
            errors.append(f"{w}: bad id {ev.get('id')!r}")
        pid = ev.get("paper_id")
        if pid not in node_ids:
            errors.append(f"{w}: paper_id {pid} not a node")
        if ev.get("type") == "text_passage":
            if ev.get("source_field") == "abstract":
                text = abstracts.get(pid) or ""
                if _norm(ev.get("quote") or "") not in _norm(text):
                    errors.append(f"{w}: quote not contained in the node's abstract")
            elif ev.get("source_field") == "title":
                if _norm(ev.get("quote") or "") != _norm(titles.get(pid) or ""):
                    errors.append(f"{w}: title quote does not match the node title")
            else:
                errors.append(f"{w}: source_field {ev.get('source_field')!r}")
        for rid in ev.get("referenced_paper_ids") or []:
            if rid not in node_ids:
                errors.append(f"{w}: referenced_paper_id {rid} not a node")
    if ev_ids and sorted(ev_ids) != [f"ev_{i:03d}" for i in range(1, len(ev_ids) + 1)]:
        errors.append("evidence ids are not a dense sequence from ev_001")
    if node_ids and sorted(node_ids) != [f"paper_{i:03d}" for i in range(1, len(node_ids) + 1)]:
        errors.append("node ids are not a dense sequence from paper_001")

    # demo strings --------------------------------------------------------
    def scan(obj, path):
        if isinstance(obj, dict):
            for k, v in obj.items():
                scan(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                scan(v, f"{path}[{i}]")
        elif isinstance(obj, str):
            for bad in DEMO_STRINGS:
                if bad.casefold() in obj.casefold():
                    errors.append(f"{path}: demo string {bad!r} present")

    scan(doc, "doc")
    return errors
