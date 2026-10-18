"""HTTP layer: disk-cached GET/POST JSON with per-host pacing and backoff.

Ported from the prototype notebook's ``http_json`` with one fix: throttle
timestamps are tracked per host, so the 1.25 s Semantic Scholar pacing and the
0.15 s OpenAlex pacing no longer cross-throttle each other.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

_RETRIES_EXHAUSTED = "RETRIES_EXHAUSTED"


class ApiError(Exception):
    """A permanent API failure (client error, or retries exhausted)."""

    def __init__(self, code, url: str, message: str = "") -> None:
        self.code = code
        self.url = url
        super().__init__(f"[{code}] {url[:120]} {message}".strip())


class Http:
    def __init__(self, cache_dir: Path, mailto: str, user_agent: str = "scinapse/0.1") -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.mailto = mailto
        self.user_agent = user_agent
        self._last_call: dict[str, float] = {}

    # -- disk cache ---------------------------------------------------------

    def cache_path(self, *parts, suffix: str = ".json") -> Path:
        h = hashlib.sha1()
        for p in parts:
            h.update(str(p).encode("utf-8"))
            h.update(b"\x00")
        return self.cache_dir / (h.hexdigest()[:20] + suffix)

    # -- requests -----------------------------------------------------------

    def get_json(
        self,
        url: str,
        *,
        headers: dict | None = None,
        min_interval: float = 1.25,
        retries: int = 7,
        cache: bool = True,
    ) -> dict:
        key = self.cache_path(url)
        if cache and key.exists():
            return json.loads(key.read_text(encoding="utf-8"))
        hdrs = {
            "User-Agent": f"{self.user_agent}; mailto:{self.mailto}",
            "Accept": "application/json",
        }
        if headers:
            hdrs.update(headers)
        host = urlsplit(url).netloc
        for attempt in range(retries):
            gap = min_interval - (time.time() - self._last_call.get(host, 0.0))
            if gap > 0:
                time.sleep(gap)
            self._last_call[host] = time.time()
            try:
                req = Request(url, headers=hdrs, method="GET")
                with urlopen(req, timeout=60) as resp:
                    payload = json.load(resp)
                if cache:
                    key.write_text(json.dumps(payload), encoding="utf-8")
                return payload
            except HTTPError as e:
                permanent = e.code in (400, 403, 404, 422)
                if permanent or attempt == retries - 1:
                    raise ApiError(e.code, url) from e
                self._backoff(attempt, e.code, url)
            except Exception as e:  # timeouts, connection resets
                if attempt == retries - 1:
                    raise ApiError(_RETRIES_EXHAUSTED, url, type(e).__name__) from e
                self._backoff(attempt, None, url)
        raise ApiError(_RETRIES_EXHAUSTED, url)  # unreachable

    def post_json(self, url: str, data: dict, *, headers: dict | None = None,
                  min_interval: float = 0.5, retries: int = 3) -> dict:
        body = json.dumps(data).encode("utf-8")
        hdrs = {
            "User-Agent": f"{self.user_agent}; mailto:{self.mailto}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if headers:
            hdrs.update(headers)
        host = urlsplit(url).netloc
        for attempt in range(retries):
            gap = min_interval - (time.time() - self._last_call.get(host, 0.0))
            if gap > 0:
                time.sleep(gap)
            self._last_call[host] = time.time()
            try:
                req = Request(url, data=body, headers=hdrs, method="POST")
                with urlopen(req, timeout=120) as resp:
                    return json.load(resp)
            except HTTPError as e:
                if e.code in (400, 401, 403, 404, 422) or attempt == retries - 1:
                    raise ApiError(e.code, url) from e
                self._backoff(attempt, e.code, url)
            except Exception as e:
                if attempt == retries - 1:
                    raise ApiError(_RETRIES_EXHAUSTED, url, type(e).__name__) from e
                self._backoff(attempt, None, url)
        raise ApiError(_RETRIES_EXHAUSTED, url)  # unreachable

    @staticmethod
    def _backoff(attempt: int, code, url: str) -> None:
        wait = min(2 ** attempt + 1, 30)
        print(f"    [{code or 'network'}] retry in {wait}s: {url[:80]}", flush=True)
        time.sleep(wait)


def query_url(base: str, path: str, params: dict) -> str:
    return f"{base}{path}?{urlencode(params)}"
