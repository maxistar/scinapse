"""OpenAlex client + record normalizers (single-record endpoints only — free)."""

from __future__ import annotations

from .httpjson import ApiError, Http, query_url

OA = "https://api.openalex.org"

WORK_SELECT = "id,doi,authorships,topics,type,referenced_works,is_retracted,primary_location"


def _tail(url: str | None) -> str | None:
    return url.rsplit("/", 1)[-1] if url else None


class OpenAlexClient:
    def __init__(self, http: Http, min_interval: float = 0.15, mailto: str = "") -> None:
        self.http = http
        self.min_interval = min_interval
        self.mailto = mailto

    def _get(self, path: str, **params) -> dict | None:
        params.setdefault("mailto", self.mailto)
        try:
            return self.http.get_json(
                query_url(OA, path, params),
                min_interval=self.min_interval, retries=4,
            )
        except ApiError as e:
            if e.code in (400, 404):
                return None  # unknown record — not an error for the pipeline
            raise

    def get_work(self, doi: str) -> dict | None:
        return self._get(f"/works/doi:{doi}", select=WORK_SELECT)

    def get_source(self, source_id: str) -> dict | None:
        # small record, no select: summary_stats.h_index and counts_by_year needed
        return self._get(f"/sources/{source_id}")


def normalize_authorships(work: dict) -> list[dict]:
    """[{key, name, orcid, inst_keys}] — key is the OpenAlex author id."""
    out = []
    for a in work.get("authorships") or []:
        author = a.get("author") or {}
        key = _tail(author.get("id"))
        inst_keys = []
        for inst in a.get("institutions") or []:
            ik = _tail(inst.get("id"))
            if ik:
                inst_keys.append(ik)
        orcid = author.get("orcid")
        out.append({
            "key": key,
            "name": author.get("display_name") or a.get("raw_author_name") or "",
            "orcid": _tail(orcid) if orcid else None,
            "inst_keys": inst_keys,
            "position": a.get("author_position"),
        })
    return out


def normalize_institutions(work: dict) -> list[dict]:
    """Deduped [{key, name, ror}] across all authorships, first-seen order."""
    seen: dict[str, dict] = {}
    for a in work.get("authorships") or []:
        for inst in a.get("institutions") or []:
            key = _tail(inst.get("id"))
            if not key or key in seen:
                continue
            seen[key] = {
                "key": key,
                "name": inst.get("display_name") or "",
                "ror": _tail(inst.get("ror")),
            }
    return list(seen.values())


def normalize_topics(work: dict, *, cap: int = 4, min_score: float = 0.2) -> list[str]:
    topics = [t for t in (work.get("topics") or []) if (t.get("score") or 0) >= min_score]
    topics.sort(key=lambda t: -(t.get("score") or 0))
    return [t["display_name"] for t in topics[:cap] if t.get("display_name")]


def referenced_works(work: dict) -> set[str]:
    return {w.rsplit("/", 1)[-1] for w in work.get("referenced_works") or []}


def source_of(work: dict) -> dict | None:
    return ((work.get("primary_location") or {}).get("source")) or None


PUB_TYPE_MAP = {
    "article": "journal_article",
    "preprint": "preprint",
    "review-article": "review_article",
}


def publication_type(work: dict | None, s2_publication_types: list | None) -> str:
    if work:
        return PUB_TYPE_MAP.get(work.get("type") or "", "other")
    for t in s2_publication_types or []:
        if t == "JournalArticle":
            return "journal_article"
        if t == "Review":
            return "review_article"
    return "unknown"
