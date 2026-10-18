"""Web-search entry tests — network-free (fake S2/Tavily/Token Factory clients)."""

from __future__ import annotations

import json

import numpy as np
import pytest

from scinapse.config import BuildConfig
from scinapse.discovery import GraphState, PaperRec, finalize
from scinapse.edges import build_similarity_edges
from scinapse.httpjson import ApiError, Http
from scinapse.similarity import SimResult
from scinapse import warnings as W
from scinapse.websearch import (
    add_web_entry,
    build_queries_llm,
    build_queries_tfidf,
    collect_candidates,
    extract_identifiers,
)
from scinapse.tavily import TavilyClient

SHA = "0f05aec1c9b1e26b16e5e6a3d5866eaebfd96f95"


def _paper(pid: str, title: str, **kw) -> dict:
    return {"paperId": pid, "title": title, "year": kw.get("year", 2024),
            "venue": kw.get("venue", ""), "citationCount": kw.get("cites", 0),
            "abstract": kw.get("abstract", "Single-cell melanoma immune profiling."),
            "authors": [{"authorId": "a1", "name": "A. Author"}],
            "externalIds": {"DOI": kw.get("doi")}}


def _state(**cfg_kw) -> GraphState:
    cfg = BuildConfig(seeds=("10.1/seed-a",),
                      question="Which single-cell methods help study melanoma immune cells?",
                      **cfg_kw)
    state = GraphState(cfg=cfg)
    state.papers["seed0001"] = PaperRec(
        s2_id="seed0001", title="Single-cell atlas of melanoma immune cells.",
        year=2020, venue="Nature", citation_count=500,
        abstract="Single-cell RNA sequencing of melanoma reveals T cell infiltration.",
        abstract_provenance="semantic_scholar", authors_s2=[("a1", "A. Author")],
        doi="10.1/seed-a", pmid=None, pmcid=None, is_seed=True, layer=0)
    return state


# -- identifier extraction --------------------------------------------------


def test_extract_identifiers_arxiv_variants():
    for url in ("https://arxiv.org/abs/2201.05242",
                "https://arxiv.org/abs/2201.05242v2",
                "https://www.arxiv.org/pdf/2201.05242",
                "https://arxiv.org/html/2201.05242v1"):
        cands = extract_identifiers({"url": url, "title": "t", "content": "", "score": 0.9})
        assert [(c.kind, c.value) for c in cands] == [("arxiv", "2201.05242")], url


def test_extract_identifiers_doi_pubmed_biorxiv_s2():
    cases = {
        "https://doi.org/10.1038/s41586-021-03704-y": ("doi", "10.1038/s41586-021-03704-y"),
        "https://dx.doi.org/10.1126/science.aad0501.": ("doi", "10.1126/science.aad0501"),
        "https://doi.org/10.1126%2Fscience.aad0501": ("doi", "10.1126/science.aad0501"),
        "https://pubmed.ncbi.nlm.nih.gov/37658464/": ("pmid", "37658464"),
        "https://www.biorxiv.org/content/10.1101/2024.01.01.573442v1": ("doi", "10.1101/2024.01.01.573442"),
        f"https://www.semanticscholar.org/paper/{SHA}/Title": ("s2", SHA),
    }
    for url, expected in cases.items():
        cands = extract_identifiers({"url": url, "title": "t", "content": "", "score": 0.5})
        assert (cands[0].kind, cands[0].value) == expected, url


def test_extract_identifiers_bare_doi_fallback():
    r = {"url": "https://www.nature.com/articles/s41586-021-03704-y",
         "title": "A paper", "content": "See https://doi.org/10.1038/s41586-021-03704-y).",
         "score": 0.7}
    cands = extract_identifiers(r)
    assert [(c.kind, c.value) for c in cands] == [("doi", "10.1038/s41586-021-03704-y")]


def test_collect_candidates_dedupe_and_order():
    results = [
        {"url": "https://doi.org/10.1234/aaa", "title": "A", "content": "", "score": 0.4},
        {"url": "https://arxiv.org/abs/2201.05242", "title": "B", "content": "", "score": 0.9},
        {"url": "https://doi.org/10.1234/aaa", "title": "A again", "content": "", "score": 0.6},
        {"url": "https://www.nature.com/news", "title": "News", "content": "no ids", "score": 0.8},
        {"url": "https://www.cell.com/fulltext", "title": "News", "content": "", "score": 0.1},
    ]
    candidates, title_pool = collect_candidates(results)
    assert [(c.kind, c.value, c.score) for c in candidates] == [
        ("arxiv", "2201.05242", 0.9), ("doi", "10.1234/aaa", 0.6)]
    assert [r["url"] for r in title_pool] == ["https://www.nature.com/news"]  # dedup + score order


# -- query construction ------------------------------------------------------


def test_build_queries_tfidf_deterministic():
    state = _state()
    q1 = build_queries_tfidf(state, 3)
    q2 = build_queries_tfidf(state, 3)
    assert q1 == q2 and 1 <= len(q1) <= 3
    assert "melanoma" in q1[0]  # question term present in the seed vocabulary


def test_build_queries_tfidf_degenerate_seeds():
    state = _state()
    state.papers["seed0001"].title = "???"
    state.papers["seed0001"].abstract = ""
    assert build_queries_tfidf(state, 3) == [state.cfg.question]


class _FakeChat:
    def __init__(self, content=None, error=False):
        self.content, self.error, self.calls = content, error, 0

    def create(self, **kw):
        self.calls += 1
        if self.error:
            raise RuntimeError("boom")
        message = type("M", (), {"content": self.content})()
        choice = type("C", (), {"message": message, "finish_reason": "stop"})()
        return type("R", (), {"choices": [choice]})()


class _FakeTf:
    def __init__(self, chat):
        self.chat = type("C", (), {"completions": chat})()


def test_build_queries_llm_parses_json(tmp_path):
    chat = _FakeChat('{"queries": ["single cell melanoma atlas", "T cell exhaustion methods"]}')
    state = _state()
    queries = build_queries_llm(state.cfg, state, _FakeTf(chat), Http(tmp_path, "t"))
    assert queries == ["single cell melanoma atlas", "T cell exhaustion methods"]


def test_build_queries_llm_failure_paths(tmp_path):
    state = _state()
    http = Http(tmp_path, "t")
    assert build_queries_llm(state.cfg, state, None, http) == []          # no client
    assert build_queries_llm(state.cfg, state, _FakeTf(_FakeChat("garbage")), http) == []
    assert build_queries_llm(state.cfg, state, _FakeTf(_FakeChat(error=True)), http) == []


def test_build_queries_llm_cache_hit_skips_client(tmp_path):
    state = _state()
    http = Http(tmp_path, "t")
    chat = _FakeChat('{"queries": ["cached query about melanoma cells"]}')
    client = _FakeTf(chat)
    assert build_queries_llm(state.cfg, state, client, http) == ["cached query about melanoma cells"]
    chat.calls = 0
    again = build_queries_llm(state.cfg, state, client, http)
    assert again == ["cached query about melanoma cells"] and chat.calls == 0


# -- Tavily client ------------------------------------------------------------


class _RecordingHttp(Http):
    def __init__(self, cache_dir):
        super().__init__(cache_dir, "t")
        self.posts = []

    def post_json(self, url, data, **kw):
        self.posts.append((url, data, kw))
        return {"results": [{"title": "R", "url": "https://arxiv.org/abs/2201.05242",
                             "content": "", "score": 0.5}]}


def test_tavily_client_cache_and_shape(tmp_path):
    http = _RecordingHttp(tmp_path)
    tav = TavilyClient(http, "tvly-test", min_interval=0.0)
    res = tav.search("q", max_results=5, include_domains=("arxiv.org",))
    assert len(res) == 1 and res[0]["url"].endswith("2201.05242")
    url, data, kw = http.posts[0]
    assert url == "https://api.tavily.com/search"
    assert data["query"] == "q" and data["max_results"] == 5
    assert data["include_domains"] == ["arxiv.org"] and data["include_published_date"] is True
    assert kw["headers"] == {"Authorization": "Bearer tvly-test"}
    http.posts.clear()
    again = tav.search("q", max_results=5, include_domains=("arxiv.org",))
    assert again == res and http.posts == []  # served from the disk cache


def test_tavily_client_raises_apierror(tmp_path):
    class _FailingHttp(Http):
        def post_json(self, url, data, **kw):
            raise ApiError(432, url)
    tav = TavilyClient(_FailingHttp(tmp_path, "t"), "k", min_interval=0.0)
    with pytest.raises(ApiError):
        tav.search("q")


# -- the pipeline step --------------------------------------------------------


class FakeS2:
    def __init__(self, papers=(), matched=None):
        self.by_doi = {p["externalIds"]["DOI"]: p for p in papers}
        self.by_arxiv = {p["externalIds"].get("ArXiv"): p for p in papers
                         if p["externalIds"].get("ArXiv")}
        self.matched = matched or {}
        self.title_calls = []

    def fetch_paper_by_doi(self, doi):
        if doi in self.by_doi:
            return self.by_doi[doi]
        raise ApiError(404, "x")

    def fetch_paper_by_arxiv(self, aid):
        if aid in self.by_arxiv:
            return self.by_arxiv[aid]
        raise ApiError(404, "x")

    def fetch_paper(self, pid):
        raise ApiError(404, "x")

    def fetch_paper_by_pmid(self, pmid):
        raise ApiError(404, "x")

    def match_paper_by_title(self, title):
        self.title_calls.append(title)
        return self.matched.get(title)


class FakeTavily:
    def __init__(self, results):
        self.results = results

    def search(self, query, *, max_results=8, include_domains=()):
        return self.results


def test_add_web_entry_pins_web_papers():
    state = _state(websearch_pinned=1)
    p1 = _paper("web0001", "Web paper one", doi="10.1234/web1", cites=7)
    p2 = _paper("web0002", "Web paper two", doi="10.1234/web2")
    s2 = FakeS2(papers=[p1, p2])
    tav = FakeTavily([
        {"url": "https://doi.org/10.1234/web1", "title": "Web paper one", "content": "", "score": 0.9},
        {"url": "https://doi.org/10.1234/web2", "title": "Web paper two", "content": "", "score": 0.5},
    ])
    add_web_entry(state, s2, tav)
    assert "web0001" in state.papers  # higher Tavily score first, cap 1
    assert "web0002" not in state.papers
    rec = state.papers["web0001"]
    assert rec.entry == "web" and rec.layer == state.cfg.layers and not rec.is_seed


def test_add_web_entry_skips_existing_and_uses_title_fallback():
    state = _state(websearch_pinned=2, websearch_title_matches=1)
    known = PaperRec(
        s2_id="seed0002", title="Already present", year=2021, venue="", citation_count=10,
        abstract="Single-cell melanoma.", abstract_provenance="semantic_scholar",
        authors_s2=[], doi="10.1234/known", pmid=None, pmcid=None, layer=1)
    state.papers["seed0002"] = known
    fresh = _paper("web0002", "Fresh from title match", doi="10.1234/fresh")
    s2 = FakeS2(matched={"Nature news page": fresh})
    tav = FakeTavily([
        {"url": "https://doi.org/10.1234/known", "title": "Already present", "content": "", "score": 0.9},
        {"url": "https://www.nature.com/news", "title": "Nature news page", "content": "", "score": 0.4},
    ])
    add_web_entry(state, s2, tav)
    assert "seed0002" in state.papers and state.papers["seed0002"].entry is None
    assert "web0002" in state.papers and state.papers["web0002"].entry == "web"


def test_add_web_entry_unavailable_paths():
    state = _state()
    add_web_entry(state, FakeS2(), None)  # enabled but no client
    assert state.warnings.has(W.WEBSEARCH_UNAVAILABLE)
    state2 = _state(websearch_enabled=False)
    add_web_entry(state2, FakeS2(), None)  # explicit --no-websearch: quiet
    assert not state2.warnings.has(W.WEBSEARCH_UNAVAILABLE)

    class _Boom:
        def search(self, *a, **kw):
            raise ApiError(432, "https://api.tavily.com/search")
    state3 = _state()
    add_web_entry(state3, FakeS2(), _Boom())
    assert state3.warnings.has(W.WEBSEARCH_UNAVAILABLE) and len(state3.papers) == 1


def test_finalize_evidence_for_web_entry():
    state = _state()
    web = PaperRec(
        s2_id="web0001", title="Web paper.", year=2026, venue="", citation_count=0,
        abstract="Single-cell melanoma.", abstract_provenance="semantic_scholar",
        authors_s2=[], doi=None, pmid=None, pmcid=None, entry="web", layer=3)
    web.sem = 0.4
    state.papers["web0001"] = web
    finalize(state, [])
    assert any("entered by web" in line for line in web.evidence_lines)
    assert web.composite is not None and 0 <= web.composite <= 100


# -- guaranteed web-entry seed edges ------------------------------------------


def _sim(state: GraphState, matrix: np.ndarray) -> SimResult:
    return SimResult(matrix=np.asarray(matrix, dtype=float), ids=list(state.papers),
                     method_version="tfidf-cosine-v1", threshold=0.9)


def test_similarity_edges_force_web_seed_connection():
    state = _state()
    state.papers["web0001"] = PaperRec(
        s2_id="web0001", title="Web paper.", year=2026, venue="", citation_count=0,
        abstract="Single-cell melanoma T cells.", abstract_provenance="semantic_scholar",
        authors_s2=[], doi=None, pmid=None, pmcid=None, entry="web", layer=3)
    edges = build_similarity_edges(state, _sim(state, [[1.0, 0.30], [0.30, 1.0]]))
    web_edges = [e for e in edges if "web0001" in (e.src, e.dst)]
    assert len(web_edges) == 1
    e = web_edges[0]
    assert e.type == "similar_to" and e.strength_value == round((0.30 + 1) / 2, 4)
    assert e.components["below_threshold"] is True and e.components["raw_cosine"] == 0.30
    assert "seed0001" in (e.src, e.dst)


def test_similarity_edges_skip_unrelated_web_paper():
    state = _state()
    state.papers["web0001"] = PaperRec(
        s2_id="web0001", title="Totally unrelated quantum computing.", year=2026, venue="",
        citation_count=0, abstract="Qubits and error correction.", abstract_provenance="none",
        authors_s2=[], doi=None, pmid=None, pmcid=None, entry="web", layer=3)
    edges = build_similarity_edges(state, _sim(state, [[1.0, 0.01], [0.01, 1.0]]))
    assert [e for e in edges if "web0001" in (e.src, e.dst)] == []  # below the 0.05 floor


def test_similarity_edges_do_not_force_for_non_web_papers():
    state = _state()
    state.papers["plain01"] = PaperRec(
        s2_id="plain01", title="Plain discovered paper.", year=2023, venue="", citation_count=1,
        abstract="Single-cell melanoma T cells.", abstract_provenance="semantic_scholar",
        authors_s2=[], doi=None, pmid=None, pmcid=None, layer=1)
    edges = build_similarity_edges(state, _sim(state, [[1.0, 0.30], [0.30, 1.0]]))
    assert [e for e in edges if "plain01" in (e.src, e.dst)] == []  # threshold 0.9 holds
