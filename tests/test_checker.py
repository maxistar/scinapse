"""Checker self-tests + a network-free serializer end-to-end test."""

from __future__ import annotations

import json
from pathlib import Path

from scinapse.checker import check, check_key_order
from scinapse.config import BuildConfig
from scinapse.discovery import GraphState, PaperRec
from scinapse.edges import EdgeDraft
from scinapse.serialize import build_document

SAMPLE = Path(__file__).resolve().parents[1] / "sample_response.json"


def test_sample_key_order_conformance():
    """The structural expectations are derived from the sample — prove it."""
    doc = json.loads(SAMPLE.read_text(encoding="utf-8"))
    assert check_key_order(doc) == []


def _minimal_document():
    cfg = BuildConfig(seeds=("10.1/seed-a",), question="test question?")
    state = GraphState(cfg=cfg)
    a = PaperRec(
        s2_id="aaaa0001", title="Seed paper about melanoma single cells.", year=2019,
        venue="Nature", citation_count=100,
        abstract="We used single-cell RNA sequencing to study melanoma. We found T cells.",
        abstract_provenance="semantic_scholar", authors_s2=[("1", "Alice A")],
        doi="10.1/seed-a", pmid=None, pmcid=None, is_seed=True, layer=0,
        authorships=[{"key": "A1", "name": "Alice A", "orcid": None, "inst_keys": ["I1"]}],
        institutions=[{"key": "I1", "name": "Institute One", "ror": None}],
        oa_work_url="https://openalex.org/W111",
    )
    b = PaperRec(
        s2_id="bbbb0002", title="Later paper on T cells.", year=2024,
        venue="Cell", citation_count=3,
        abstract="", abstract_provenance="none", authors_s2=[("2", "Bob B")],
        doi="10.1/later-b", pmid=None, pmcid=None, is_seed=False, layer=1,
    )
    state.papers[a.s2_id] = a
    state.papers[b.s2_id] = b
    state.citation_pairs.add((b.s2_id, a.s2_id))  # b cites a (verified)
    a.evidence_lines = ["seed paper — your starting collection"]
    b.evidence_lines = ["cites 1 seed paper(s): Seed paper about melanoma single cells."]
    drafts = [
        EdgeDraft(src=b.s2_id, dst=a.s2_id, type="citation_overlap", directed=True,
                  strength_value=1.0, metric="citation_overlap_v1", range_=(0, 1),
                  method_version="citation-max-fusion-v1",
                  components={"direct_cite": True, "reference_jaccard": None,
                              "intersection_count": None, "union_count": None},
                  direct_cite=True),
        EdgeDraft(src=a.s2_id, dst=b.s2_id, type="similar_to", directed=False,
                  strength_value=0.62, metric="abstract_cosine_similarity", range_=(0, 1),
                  method_version="tfidf-cosine-v1+map01", components={"raw_cosine": 0.24}),
        EdgeDraft(src=a.s2_id, dst=b.s2_id, type="shared_author", directed=False,
                  strength_value=0.5, metric="author_overlap_salton", range_=(0, 1),
                  method_version="author-salton-v1",
                  components={"shared_author_names": ["Alice A"], "shared_authors_count": 1,
                              "author_counts": [1, 1]}),
    ]
    return build_document(state, drafts)


def test_generated_document_passes_check():
    doc = _minimal_document()
    errors = check(doc)
    assert errors == []


def test_generated_document_degraded_paths():
    """No LLM -> null dimensions + uncertain; no abstract -> title quote path."""
    doc = _minimal_document()
    a, b = doc["nodes"]
    assert b["relevance"]["dimensions"] == {k: None for k in a["relevance"]["dimensions"]}
    assert b["relevance"]["score"] is None
    assert b["relevance"]["assessment"] == "uncertain"
    assert b["relevance"]["status"] == "insufficient_evidence"
    assert b["abstract"] is None and b["abstract_available"] is False
    title_ev = [e for e in doc["evidence"] if e["paper_id"] == b["id"]
                and e["type"] == "text_passage"][0]
    assert title_ev["source_field"] == "title" and title_ev["quote"] == b["title"]
    abstract_ev = [e for e in doc["evidence"] if e["paper_id"] == a["id"]
                   and e["type"] == "text_passage"][0]
    assert abstract_ev["quote"] in a["abstract"]["text"]


def test_integrity_failure_detected():
    doc = _minimal_document()
    doc["edges"][0]["target"] = "paper_999"
    errors = check(doc)
    assert any("endpoint not a node" in e for e in errors)


def test_formula_failure_detected():
    doc = _minimal_document()
    node = doc["nodes"][0]
    node["relevance"]["dimensions"] = {
        "research_question_alignment": 1.0, "disease_setting_alignment": 1.0,
        "method_alignment": 1.0, "outcome_alignment": 1.0,
    }
    node["relevance"]["score"] = 0.42  # wrong: rubric says 1.0
    errors = check(doc)
    assert any("weighted rubric" in e for e in errors)
    assert any("!= bucket" in e for e in errors)


def test_display_score_must_mirror_strength():
    doc = _minimal_document()
    doc["edges"][1]["display_score"]["value"] = 0.99
    errors = check(doc)
    assert any("display_score.value" in e for e in errors)


def test_quote_containment_enforced():
    doc = _minimal_document()
    ev = [e for e in doc["evidence"] if e.get("source_field") == "abstract"][0]
    ev["quote"] = "This sentence is not in the abstract."
    errors = check(doc)
    assert any("quote not contained" in e for e in errors)
