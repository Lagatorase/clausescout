"""The verbatim grounding check: every quoted span must really be in the contract.

Invented legal text is the failure lawyers fear most, so any span a method returns has to appear
in the contract word for word. The only differences I forgive are ones that never change the
wording:
- whitespace: line breaks, tabs, repeated or non-breaking spaces, and a space left after a
  hyphen by a line break ("non- exclusive" for "non-exclusive")
- curly versus straight quotes
- Unicode presentation forms (ligatures like U+FB01 for "fi", look-alikes like the Greek
  question mark for a semicolon, full-width characters), via Unicode compatibility
  normalisation, and soft hyphens, which are invisible line-break hints
Case, punctuation, dashes and spelling all have to match. Spans that fail are rejected and
counted, never repaired.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field, replace

from clausescout.findings import Finding

_QUOTES = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"',
})
_SOFT_HYPHEN = "\u00ad"


def _normalised_chars(text: str) -> list[tuple[str, int]]:
    """Each normalised character with the index of the original character it came from.

    The quote and the contract both go through this one function, so they are always
    normalised the same way.
    """
    out: list[tuple[str, int]] = []
    for i, ch in enumerate(text):
        # NFKD per character splits ligatures and maps look-alikes, and decomposes accents the
        # same way whether the text stored them composed or as a separate combining mark.
        for c in unicodedata.normalize("NFKD", ch).translate(_QUOTES):
            if c == _SOFT_HYPHEN:
                continue
            if c.isspace():
                prev = out[-1][0] if out else " "
                # One space per whitespace run, and none straight after a word's hyphen.
                if prev == " ":
                    continue
                if prev == "-" and len(out) > 1 and out[-2][0].isalnum():
                    continue
                c = " "
            out.append((c, i))
    return out


def normalise(text: str) -> str:
    """The text as the grounding check compares it. Only the forgiven differences change."""
    return "".join(c for c, _ in _normalised_chars(text)).strip()


class GroundingIndex:
    """A normalised copy of one contract, with a map back to the original character offsets."""

    def __init__(self, text: str):
        self.text = text
        chars = _normalised_chars(text)
        self.norm = "".join(c for c, _ in chars)
        self._orig = [i for _, i in chars]

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
        # The quote never ends in a space, and its last character came from one original
        # character, so the span ends just after that one.
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
