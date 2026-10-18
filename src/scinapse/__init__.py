"""Scinapse — build a research-paper discovery graph (JSON) from seed papers."""

from .config import BuildConfig, exploration_id, load_dotenv, normalize_doi

__version__ = "0.1.0"
__all__ = ["BuildConfig", "build_graph", "exploration_id", "load_dotenv", "normalize_doi"]


def build_graph(seeds, question: str, **overrides) -> dict:
    """Seeds in -> sample_response.json-shaped document out (dict)."""
    from .pipeline import run  # deferred: heavy imports (sklearn) stay optional
    cfg = BuildConfig(seeds=tuple(seeds), question=question, **overrides)
    return run(cfg)
