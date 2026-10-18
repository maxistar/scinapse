"""Build configuration, environment handling, and derived identifiers."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, replace
from pathlib import Path

DEFAULT_MAILTO = "nonvisual.wrk@gmail.com"  # polite-pool identifier for both APIs
DEFAULT_CHAT_MODEL = "nvidia/nemotron-3-super-120b-a12b"  # JSON-mode capable on Token Factory

_DOI_PREFIXES = ("https://doi.org/", "http://doi.org/", "doi.org/", "DOI:", "doi:")


def normalize_doi(doi: str) -> str:
    """Strip URL/scheme decorations from a user-supplied DOI."""
    d = (doi or "").strip()
    lowered = d.lower()
    for prefix in _DOI_PREFIXES:
        if lowered.startswith(prefix.lower()):
            d = d[len(prefix):]
            lowered = d.lower()
    return d.strip()


def load_dotenv(path: Path | None = None) -> None:
    """Minimal .env loader: KEY=VALUE lines, no overrides of existing env."""
    p = path or Path(".env")
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def nebius_api_key() -> str | None:
    return os.environ.get("NEBIUS_API_KEY") or None


def s2_api_key() -> str | None:
    """Optional Semantic Scholar key — raises the shared-pool rate ceiling."""
    return os.environ.get("S2_API_KEY") or None


@dataclass(frozen=True)
class BuildConfig:
    seeds: tuple[str, ...]
    question: str
    layers: int = 3
    top_k_per_layer: int = 8
    top_entry_n: int = 6
    recent_min_year: int = 2025
    cache_dir: Path = Path(".scinapse_cache")
    mailto: str = DEFAULT_MAILTO
    chat_model: str = DEFAULT_CHAT_MODEL
    embed_model: str = ""  # "" -> TF-IDF fallback
    llm_limit: int = 40  # max LLM-assessed nodes (priority: seeds, then composite)
    s2_min_interval: float = 1.25
    oa_min_interval: float = 0.15
    # similarity edges
    sim_top_k: int = 2
    sim_threshold_tfidf: float = 0.15
    sim_threshold_embed: float = 0.55
    # shared-author edges
    author_top_k: int = 2
    # reference-overlap component of citation edges
    refs_threshold: float = 0.08
    refs_min_intersection: int = 5
    refs_top_k: int = 3

    @property
    def normalized_seeds(self) -> tuple[str, ...]:
        return tuple(normalize_doi(s) for s in self.seeds)

    def with_env(self) -> "BuildConfig":
        """Apply SCINAPSE_* environment overrides (cache dir, mailto)."""
        updates = {}
        if env_dir := os.environ.get("SCINAPSE_CACHE_DIR"):
            updates["cache_dir"] = Path(env_dir)
        if env_mail := os.environ.get("SCINAPSE_MAILTO"):
            updates["mailto"] = env_mail
        return replace(self, **updates) if updates else self

    def smoke(self) -> "BuildConfig":
        """Tiny cheap profile mirroring the notebook's SCINAPSE_SMOKE."""
        return replace(self, layers=1, top_k_per_layer=4, top_entry_n=2, llm_limit=8)


def exploration_id(seeds: tuple[str, ...] | list[str], question: str) -> str:
    """Deterministic exploration id from the input pair (not from output data)."""
    h = hashlib.sha1()
    h.update("|".join(sorted(normalize_doi(s) for s in seeds)).encode("utf-8"))
    h.update(b"||")
    h.update((question or "").strip().casefold().encode("utf-8"))
    return "exp_" + h.hexdigest()[:12]
