"""Sequential id allocation with crosswalks (paper_NNN / author_NNN / …)."""

from __future__ import annotations


class IdAllocator:
    def __init__(self) -> None:
        self._paper: dict[str, str] = {}
        self._rev_paper: dict[str, str] = {}
        self._author: dict[str, str] = {}
        self._institution: dict[str, str] = {}
        self._ev = 0

    def paper(self, s2_id: str) -> str:
        if s2_id not in self._paper:
            self._paper[s2_id] = f"paper_{len(self._paper) + 1:03d}"
            self._rev_paper[self._paper[s2_id]] = s2_id
        return self._paper[s2_id]

    def author(self, key: str) -> str:
        if key not in self._author:
            self._author[key] = f"author_{len(self._author) + 1:03d}"
        return self._author[key]

    def institution(self, key: str) -> str:
        if key not in self._institution:
            self._institution[key] = f"institution_{len(self._institution) + 1:03d}"
        return self._institution[key]

    def next_evidence(self) -> str:
        self._ev += 1
        return f"ev_{self._ev:03d}"

    def paper_of(self, s2_id: str) -> str | None:
        return self._paper.get(s2_id)

    def s2_of(self, paper_id: str) -> str | None:
        return self._rev_paper.get(paper_id)

    @property
    def paper_count(self) -> int:
        return len(self._paper)
