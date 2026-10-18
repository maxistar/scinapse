"""Tavily web-search client — thin POST wrapper on httpjson with a manual disk cache.

``httpjson`` only caches GETs, and the free tier is metered (1 credit per basic
search), so responses are cached under a body-keyed path: reruns cost nothing.
"""

from __future__ import annotations

import json

from .httpjson import ApiError, Http

TAVILY = "https://api.tavily.com/search"


class TavilyClient:
    def __init__(self, http: Http, api_key: str, min_interval: float = 1.0) -> None:
        self.http = http
        self.api_key = api_key
        self.min_interval = min_interval

    def search(self, query: str, *, max_results: int = 8,
               include_domains: tuple[str, ...] = ()) -> list[dict]:
        """One query -> Tavily result dicts ``[{title, url, content, score, ...}]``.

        Raises ApiError on permanent failure (bad key, plan limits 432/433) or
        exhausted retries — the caller degrades to a warning.
        """
        body = {
            "query": query,
            "max_results": max_results,
            "include_domains": list(include_domains),
            "include_answer": False,
            "include_raw_content": False,
            "include_published_date": True,
        }
        key = self.http.cache_path("tavily", TAVILY, json.dumps(body, sort_keys=True))
        if key.exists():
            return _results(json.loads(key.read_text(encoding="utf-8")))
        payload = self.http.post_json(
            TAVILY, body,
            headers={"Authorization": f"Bearer {self.api_key}"},
            min_interval=self.min_interval, retries=2,
        )
        key.write_text(json.dumps(payload), encoding="utf-8")
        return _results(payload)


def _results(payload: dict) -> list[dict]:
    return [r for r in (payload.get("results") or []) if isinstance(r, dict)]
