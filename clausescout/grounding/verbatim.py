"""The verbatim grounding check: every quoted span must really be in the contract.

Invented legal text is the failure lawyers fear most, so any span a method returns has to appear
in the contract word for word. The only differences I forgive are whitespace (line breaks,
tabs, repeated or non-breaking spaces) and curly versus straight quotes, because text
extraction and models change those without changing the meaning. Case, punctuation, dashes and
spelling all have to match. Spans that fail are rejected and counted, never repaired.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field, replace

from clausescout.findings import Finding

_QUOTES = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
})
_WS = re.compile(r"\s+")


def normalise(text: str) -> str:
    """Collapses whitespace runs to one space and straightens quotes. Nothing else changes."""
    return _WS.sub(" ", text.translate(_QUOTES)).strip()


class GroundingIndex:
    """A normalised copy of one contract, with a map back to the original character offsets."""

    def __init__(self, text: str):
        self.text = text
        chars: list[str] = []
        self._orig: list[int] = []  # original index of each normalised character
        straight = text.translate(_QUOTES)
        i = 0
        while i < len(straight):
            if straight[i].isspace():
                # A whole whitespace run becomes one space that points at the run's start.
                j = i
                while j < len(straight) and straight[j].isspace():
                    j += 1
                chars.append(" ")
                self._orig.append(i)
                i = j
            else:
                chars.append(straight[i])
                self._orig.append(i)
                i += 1
        self.norm = "".join(chars)

    def find(self, quote: str, hint: int | None = None) -> tuple[int, int] | None:
        """Original (start, end) offsets of the quote, or None if it isn't in the contract.

        If the quote appears more than once I take the occurrence nearest to hint (an original
        character offset, such as where the model's chunk started), or the first one.
        """
        q = normalise(quote)
        if not q:
            return None
        hits = []
        pos = self.norm.find(q)
        while pos != -1:
            hits.append(pos)
            pos = self.norm.find(q, pos + 1)
        if not hits:
            return None
        if hint is not None:
            pos = min(hits, key=lambda h: abs(self._orig[h] - hint))
        else:
            pos = hits[0]
        # The quote never ends in a space, so its last character maps to one original character.
        return self._orig[pos], self._orig[pos + len(q) - 1] + 1


@dataclass
class GroundingStats:
    submitted: int = 0
    accepted: int = 0
    rejected: int = 0
    rejected_examples: list[Finding] = field(default_factory=list)

    @property
    def rejection_rate(self) -> float:
        return self.rejected / self.submitted if self.submitted else 0.0

    def __add__(self, other: GroundingStats) -> GroundingStats:
        return GroundingStats(
            self.submitted + other.submitted,
            self.accepted + other.accepted,
            self.rejected + other.rejected,
            self.rejected_examples + other.rejected_examples,
        )


def ground_findings(
    findings: Iterable[Finding],
    contract_text: str,
    index: GroundingIndex | None = None,
    hints: Iterable[int | None] | None = None,
) -> tuple[list[Finding], GroundingStats]:
    """Keeps only findings whose text is in the contract, with exact text and offsets filled in.

    hints, if given, is one original offset per finding to break ties between repeated text.
    """
    index = index or GroundingIndex(contract_text)
    findings = list(findings)
    hints = list(hints) if hints is not None else [None] * len(findings)
    kept, stats = [], GroundingStats()
    for f, hint in zip(findings, hints, strict=True):
        stats.submitted += 1
        span = index.find(f.text, hint)
        if span is None:
            stats.rejected += 1
            stats.rejected_examples.append(f)
            continue
        stats.accepted += 1
        start, end = span
        kept.append(replace(f, text=contract_text[start:end], start=start, end=end))
    return kept, stats
