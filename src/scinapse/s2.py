"""Semantic Scholar Graph API client (no key required; shared pool — paced)."""

from __future__ import annotations

from .config import s2_api_key
from .httpjson import ApiError, Http, query_url

S2 = "https://api.semanticscholar.org/graph/v1"

S2_FIELDS = (
    "paperId,title,year,venue,citationCount,abstract,authors,externalIds,"
    "fieldsOfStudy,publicationTypes,publicationDate,journal,isOpenAccess,openAccessPdf,tldr"
)

# tldr is rejected by the list endpoints (citations / author papers / search)
S2_FIELDS_LIST = S2_FIELDS.replace(",tldr", "")


class S2Client:
    def __init__(self, http: Http, min_interval: float = 1.25) -> None:
        self.http = http
        self.min_interval = min_interval

    def _headers(self) -> dict:
        key = s2_api_key()
        return {"x-api-key": key} if key else {}

    def _get(self, path: str, retries: int | None = None, **params) -> dict:
        kw = {"min_interval": self.min_interval, "headers": self._headers()}
        if retries:
            kw["retries"] = retries
        return self.http.get_json(query_url(S2, path, params), **kw)

    # -- endpoints ----------------------------------------------------------

    def fetch_paper_by_doi(self, doi: str) -> dict:
        """Resolve a seed DOI. Raises ApiError(404) when unknown."""
        return self._get(f"/paper/DOI:{doi}", fields=S2_FIELDS)

    def fetch_paper(self, paper_id: str) -> dict:
        """Resolve an S2 sha id (e.g. from a semanticscholar.org URL)."""
        return self._get(f"/paper/{paper_id}", fields=S2_FIELDS)

    def fetch_paper_by_arxiv(self, arxiv_id: str) -> dict:
        return self._get(f"/paper/arXiv:{arxiv_id}", fields=S2_FIELDS)

    def fetch_paper_by_pmid(self, pmid: str) -> dict:
        return self._get(f"/paper/PMID:{pmid}", fields=S2_FIELDS)

    def match_paper_by_title(self, title: str) -> dict | None:
        """Single best title match; None when S2 has no confident match.

        Search-family endpoint (rejects ``tldr``), retried leniently.
        """
        try:
            return self._get("/paper/search/match", retries=2,
                             query=title, fields=S2_FIELDS_LIST)
        except ApiError as e:
            if e.code in (400, 404):
                return None
            raise

    def fetch_citations(self, paper_id: str, *, offset: int | None = None, limit: int = 100) -> dict:
        params = {"fields": S2_FIELDS_LIST, "limit": limit}
        if offset is not None:
            params["offset"] = offset
        return self._get(f"/paper/{paper_id}/citations", **params)

    def fetch_author_papers(self, author_id: str, limit: int = 25) -> list[dict]:
        r = self._get(f"/author/{author_id}/papers", fields=S2_FIELDS_LIST, limit=limit)
        return r.get("data") or []

    def search_papers(self, query: str, year_range: str, limit: int = 25) -> list[dict]:
        """Relevance search; retried leniently (429-prone on the shared pool)."""
        r = self._get(
            "/paper/search", retries=4, query=query, year=year_range,
            fields=S2_FIELDS_LIST, limit=limit,
        )
        return r.get("data") or []


def abstract_text(rec: dict) -> tuple[str | None, str]:
    """(text, provenance) — S2 abstract, else the S2 auto-summary (tldr)."""
    abstract = (rec.get("abstract") or "").strip()
    if abstract:
        return abstract, "semantic_scholar"
    tldr = ((rec.get("tldr") or {}).get("text") or "").strip()
    if tldr:
        return tldr, "semantic_scholar_tldr"
    return None, "none"


__all__ = ["S2Client", "S2_FIELDS", "ApiError", "abstract_text"]
