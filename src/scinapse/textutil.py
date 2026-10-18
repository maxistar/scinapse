"""Text helpers shared by the assessor (verification) and checker (enforcement).

One normalization function so a quote accepted at assessment time always passes
the checker: casefold + whitespace collapse + NFKC + typographic punctuation
folding (LLMs transcribe curly quotes and non-breaking hyphens).
"""

from __future__ import annotations

import re
import unicodedata

_FOLD = {0x2010: "-", 0x2011: "-", 0x2012: "-", 0x2013: "-", 0x2014: "-",
         0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: '"', 0x00A0: " "}

_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def normalize_text(s: str | None) -> str:
    s = unicodedata.normalize("NFKC", s or "").translate(_FOLD)
    return re.sub(r"\s+", " ", s).strip().casefold()


def normalized_contains(quote: str | None, text: str | None) -> bool:
    q = normalize_text(quote)
    return bool(q) and q in normalize_text(text)


def first_sentence(text: str | None, cap: int = 400) -> str:
    s = _SENTENCE.split((text or "").strip(), 1)[0].strip()
    return s if len(s) <= cap else s[: cap - 1] + "…"
