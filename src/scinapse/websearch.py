"""Web-search entry: Tavily queries -> scholarly identifiers -> Semantic Scholar papers.

Queries are LLM-generated (Token Factory, JSON mode) with a deterministic
TF-IDF fallback (``--no-llm``, missing key, or failed call). Tavily is
restricted to scholarly domains; hits are resolved to Semantic Scholar records
and pinned into the graph's top layer exactly like ``discovery.add_top_entry``
pins author/topic papers (``entry="web"``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from . import warnings as W
from .assess import _chat, extract_json
from .discovery import GraphState, add_paper, short_title
from .httpjson import ApiError, Http
from .s2 import S2Client
from .tavily import TavilyClient

QUERY_PROMPT = """Research question: {question}

Seed papers:
{seeds}

You are writing queries for an academic web search engine whose results are
restricted to arxiv.org, biorxiv.org, medrxiv.org, pubmed.ncbi.nlm.nih.gov and
semanticscholar.org. Return ONLY a JSON object with exactly one key:
- "queries": list of {n} distinct queries, each 4-10 words, keyword-style
  (no quotes, no boolean operators, no field prefixes like title:), together
  covering the main methods, the disease/model setting, and the outcomes of
  interest. Use terms likely to appear in paper titles and abstracts.

No markdown, no commentary — only the JSON object."""

# URL patterns tried in order; the first block that yields a candidate wins
_URL_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("s2", re.compile(r"(?:www\.)?semanticscholar\.org/paper/([0-9a-f]{40})", re.I)),
    ("doi", re.compile(r"(?:dx\.)?doi\.org/(\S+)", re.I)),
    ("arxiv", re.compile(r"(?:www\.)?arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5})(?:v\d+)?", re.I)),
    ("pmid", re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", re.I)),
    ("doi", re.compile(r"(?:www\.)?(?:bio|med)rxiv\.org/content/(\S+)", re.I)),
]
_BARE_DOI = re.compile(r"\b10\.\d{4,9}/[^\s\"'<>\[\]]+")
_TRAILING_JUNK = ".,;:>)]}\"'"


@dataclass(frozen=True)
class Candidate:
    kind: str    # "s2" | "doi" | "arxiv" | "pmid"
    value: str   # normalized identifier
    score: float  # Tavily relevance score of the result it came from


def _clean_doi(raw: str) -> str:
    """Pull a normalized DOI out of a URL path or text snippet."""
    m = _BARE_DOI.search(re.split(r"[?#]", unquote(raw))[0])
    if not m:
        return ""
    d = m.group(0).rstrip(_TRAILING_JUNK)
    if d.lower().startswith("10.1101/"):  # bio/medrxiv versions: 10.1101/...v3
        d = re.sub(r"v\d+$", "", d)
    return d


def extract_identifiers(result: dict) -> list[Candidate]:
    """Parse one Tavily result (``{title, url, content, score}``) -> candidates."""
    url = result.get("url") or ""
    score = float(result.get("score") or 0.0)
    out: list[Candidate] = []
    for kind, pat in _URL_PATTERNS:
        m = pat.search(url)
        if not m:
            continue
        if kind == "doi":
            value = _clean_doi(m.group(1))
        else:
            value = m.group(1)
        if value:
            out.append(Candidate(kind=kind, value=value, score=score))
    if not out:  # bare DOI hidden in the snippet (doi.org links redirect)
        d = _clean_doi(f'{url} {result.get("title") or ""} {result.get("content") or ""}')
        if d:
            out.append(Candidate(kind="doi", value=d, score=score))
    return out


def collect_candidates(results: list[dict]) -> tuple[list[Candidate], list[dict]]:
    """Deduped candidates sorted by Tavily score desc + the identifier-free pool."""
    best: dict[tuple[str, str], Candidate] = {}
    title_pool: list[dict] = []
    seen_titles: set[str] = set()
    for r in results:
        cands = extract_identifiers(r)
        if not cands:
            title = (r.get("title") or "").strip().lower()
            if title and title not in seen_titles:
                seen_titles.add(title)
                title_pool.append(r)
            continue
        for c in cands:
            k = (c.kind, c.value.lower())
            if k not in best or c.score > best[k].score:
                best[k] = c
    prio = {"s2": 0, "doi": 1, "arxiv": 2, "pmid": 3}
    ordered = sorted(best.values(), key=lambda c: (-c.score, prio[c.kind], c.value))
    title_pool.sort(key=lambda r: -float(r.get("score") or 0.0))
    return ordered, title_pool


def resolve_candidates(state: GraphState, s2: S2Client, candidates: list[Candidate], *,
                       title_pool: list[dict], cap: int, title_matches: int) -> tuple[list[dict], int]:
    """Resolve identifiers (and capped title fallbacks) via S2, stopping at `cap` new papers.

    Returns (paper records, non-404 ApiError count).
    """
    fetchers = {"s2": s2.fetch_paper, "doi": s2.fetch_paper_by_doi,
                "arxiv": s2.fetch_paper_by_arxiv, "pmid": s2.fetch_paper_by_pmid}
    papers: list[dict] = []
    failures = 0

    def take(p: dict | None) -> None:
        if not p:
            return
        pid = p.get("paperId")
        if pid and (p.get("title") or "").strip() and pid not in state.papers \
                and all(x.get("paperId") != pid for x in papers):
            papers.append(p)

    def resolve(kind: str, value: str) -> dict | None:
        nonlocal failures
        try:
            return fetchers[kind](value)
        except ApiError as e:
            if e.code in (400, 404):
                return None  # unknown identifier — not an error
            failures += 1
            print(f"    ! websearch resolve {kind} {value[:40]}: {e}", flush=True)
            return None

    for c in candidates:
        if len(papers) >= cap:
            break
        take(resolve(c.kind, c.value))
    for r in title_pool[:title_matches]:  # search-family endpoint — capped
        if len(papers) >= cap:
            break
        title = (r.get("title") or "").strip()
        if not title:
            continue
        try:
            take(s2.match_paper_by_title(title))
        except ApiError as e:
            failures += 1
            print(f"    ! websearch title match: {e}", flush=True)
    return papers, failures


def build_queries_llm(cfg, state: GraphState, client, http: Http) -> list[str]:
    """Keyword queries from the seed papers via Token Factory; [] on any failure."""
    if client is None or http is None:
        return []
    seeds = [r for r in state.papers.values() if r.is_seed][:5]
    if not seeds:
        return []
    seed_lines = "\n".join(
        f"- {r.title} ({r.year or 'n.d.'}) — {(r.abstract or '')[:200]}" for r in seeds)
    prompt = QUERY_PROMPT.format(question=cfg.question, seeds=seed_lines,
                                 n=cfg.websearch_queries)
    cache_key = http.cache_path("websearch-queries", cfg.chat_model, prompt, suffix=".txt")
    try:
        if cache_key.exists():
            raw = cache_key.read_text(encoding="utf-8")
        else:
            raw = _chat(client, cfg.chat_model, prompt)
            if extract_json(raw):
                cache_key.write_text(raw, encoding="utf-8")
    except Exception:
        return []
    data = extract_json(raw)
    queries = [str(q).strip() for q in (data.get("queries") or []) if str(q).strip()]
    return [q for q in queries if len(q.split()) >= 2][:cfg.websearch_queries]


def build_queries_tfidf(state: GraphState, n: int) -> list[str]:
    """Deterministic keyword queries from seed titles+abstracts and the question."""
    cfg = state.cfg
    docs = [f"{r.title}. {r.abstract}"[:1500]
            for r in state.papers.values() if r.is_seed and (r.title or r.abstract)]
    if not docs:
        return [cfg.question]
    try:
        tfv = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1,
                              sublinear_tf=True)
        X = tfv.fit_transform(docs)
    except ValueError:  # empty vocabulary (degenerate seeds)
        return [cfg.question]
    vocab = tfv.get_feature_names_out()
    agg = np.asarray(X.sum(axis=0)).ravel()
    scores = {t: float(s) for t, s in zip(vocab, agg)
              if len(t) >= 4 and any(c.isalpha() for c in t)}
    unigrams = sorted((t for t in scores if " " not in t), key=lambda t: -scores[t])
    bigrams = sorted((t for t in scores if " " in t), key=lambda t: -scores[t])
    queries = []
    qvec = tfv.transform([cfg.question])  # fold the question in via shared vocabulary
    qterms = sorted(((float(qvec[0, i]), vocab[i]) for i in qvec.nonzero()[1]
                     if len(vocab[i]) >= 4 and any(c.isalpha() for c in vocab[i])),
                    reverse=True)
    if qterms:
        queries.append(" ".join(t for _, t in qterms[:5]))
    if bigrams:
        queries.append(" ".join(bigrams[:2] + unigrams[:1]))
    if unigrams:
        queries.append(" ".join(unigrams[:4]))
    out, seen = [], set()
    for q in queries:
        q = q.strip()
        if q and q not in seen:
            seen.add(q)
            out.append(q)
    return (out or [cfg.question])[:n]


def add_web_entry(state: GraphState, s2: S2Client, tavily: TavilyClient | None,
                  tf_client=None, http: Http | None = None) -> None:
    """Pipeline step: queries -> Tavily -> identifiers -> S2 -> ``entry="web"`` pins."""
    cfg = state.cfg
    if tavily is None:
        if cfg.websearch_enabled:
            state.warnings.add(W.WEBSEARCH_UNAVAILABLE)
            print("    web search: off (no TAVILY_API_KEY)", flush=True)
        return
    queries = build_queries_llm(cfg, state, tf_client, http) if tf_client else []
    if queries:
        print(f"    queries (LLM): {queries}", flush=True)
    else:
        queries = build_queries_tfidf(state, cfg.websearch_queries)
        print(f"    queries (TF-IDF): {queries}", flush=True)
    results: list[dict] = []
    for q in queries:
        try:
            results.extend(tavily.search(q, max_results=cfg.websearch_results,
                                         include_domains=tuple(cfg.websearch_domains)))
        except ApiError as e:
            state.warnings.add(W.WEBSEARCH_UNAVAILABLE, message=str(e))
            print(f"    ! web search: {e}", flush=True)
            return  # quota/auth failures do not recover query-to-query
    candidates, title_pool = collect_candidates(results)
    print(f"    web search: {len(results)} results -> {len(candidates)} identifiers, "
          f"{len(title_pool)} title-only", flush=True)
    papers, failures = resolve_candidates(state, s2, candidates, title_pool=title_pool,
                                          cap=cfg.websearch_pinned,
                                          title_matches=cfg.websearch_title_matches)
    if failures and not papers:
        state.warnings.add(
            W.WEBSEARCH_UNAVAILABLE,
            message="Semantic Scholar resolution failed for all web-search candidates.")
    for p in papers:
        rec = add_paper(state, p, layer=cfg.layers, entry="web")
        if rec:
            print(f"    latest[{'web':>6}] {rec.year} cites={rec.citation_count:>3}  "
                  f"{short_title(rec.title, 62)}", flush=True)
    if not papers:
        print("    web search: no new papers resolved", flush=True)
