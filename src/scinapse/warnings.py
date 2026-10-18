"""Warning collection — real, deduplicated run diagnostics for the output document."""

from __future__ import annotations

from dataclasses import dataclass


SEED_RESOLUTION_FAILED = "SEED_RESOLUTION_FAILED"
ABSTRACT_UNAVAILABLE = "ABSTRACT_UNAVAILABLE"
EVIDENCE_QUOTE_ADJUSTED = "EVIDENCE_QUOTE_ADJUSTED"
LLM_ASSESSMENT_FAILED = "LLM_ASSESSMENT_FAILED"
LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
OPENALEX_UNMATCHED = "OPENALEX_UNMATCHED"
S2_RATE_LIMITED = "S2_RATE_LIMITED"
TOPIC_SEARCH_UNAVAILABLE = "TOPIC_SEARCH_UNAVAILABLE"
PARTIAL_QUALITY_ASSESSMENT = "PARTIAL_QUALITY_ASSESSMENT"

MESSAGES = {
    SEED_RESOLUTION_FAILED: "Seed DOI could not be resolved on Semantic Scholar.",
    ABSTRACT_UNAVAILABLE: "Relevance and research quality cannot be adequately assessed from the retrieved title.",
    EVIDENCE_QUOTE_ADJUSTED: "The selected quote was not found verbatim in the abstract; the opening sentence is used instead.",
    LLM_ASSESSMENT_FAILED: "The LLM assessment failed; relevance dimensions are unavailable for this paper.",
    LLM_UNAVAILABLE: "No Token Factory API key is configured; evidence templates are used instead of LLM assessments.",
    OPENALEX_UNMATCHED: "DOI not matched on OpenAlex; affiliations, topics, and reference lists are unavailable.",
    S2_RATE_LIMITED: "A Semantic Scholar request exhausted its retries and was skipped.",
    TOPIC_SEARCH_UNAVAILABLE: "Topic search failed; latest-by-author entry is still applied.",
    PARTIAL_QUALITY_ASSESSMENT: "Quality dimensions are assessed from abstracts only; full text was not inspected.",
}


@dataclass(frozen=True)
class BuildWarning:
    code: str
    message: str
    node_id: str | None = None

    def to_json(self) -> dict:
        return {"code": self.code, "node_id": self.node_id, "message": self.message}


class WarningCollector:
    def __init__(self) -> None:
        self._items: list[BuildWarning] = []

    def add(self, code: str, node_id: str | None = None, message: str | None = None) -> None:
        self._items.append(BuildWarning(code, message or MESSAGES.get(code, code), node_id))

    def has(self, code: str, node_id: str | None = None) -> bool:
        return any(w.code == code and w.node_id == node_id for w in self._items)

    def to_json(self) -> list[dict]:
        """Deduplicated, deterministically ordered (code, then node id)."""
        seen, out = set(), []
        for w in sorted(self._items, key=lambda w: (w.code, w.node_id or "")):
            key = (w.code, w.node_id)
            if key in seen:
                continue
            seen.add(key)
            out.append(w.to_json())
        return out
