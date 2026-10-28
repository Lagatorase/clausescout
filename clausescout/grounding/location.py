"""Mapping a character span to the page or paragraph a lawyer would cite."""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass


@dataclass
class Segment:
    kind: str  # "page" or "paragraph"
    number: int
    start: int
    end: int


@dataclass
class Location:
    kind: str
    first: int
    last: int

    @property
    def label(self) -> str:
        short = {"page": ("p.", "pp."), "paragraph": ("para.", "paras.")}[self.kind]
        if self.first == self.last:
            return f"{short[0]} {self.first}"
        return f"{short[1]} {self.first}-{self.last}"


_BLANK_LINE = re.compile(r"\n[ \t\r\f\v]*\n\s*")


def paragraph_segments(text: str) -> list[Segment]:
    """Splits plain text into paragraphs at blank lines and numbers the non-empty ones."""
    segments, pos = [], 0
    for m in [*_BLANK_LINE.finditer(text), None]:
        end = m.start() if m else len(text)
        block = text[pos:end]
        if block.strip():
            # I trim surrounding whitespace so the segment covers just the paragraph's text.
            lead = len(block) - len(block.lstrip())
            segments.append(Segment("paragraph", len(segments) + 1, pos + lead,
                                    pos + len(block.rstrip())))
        if m:
            pos = m.end()
    return segments


def locate(segments: list[Segment], start: int, end: int) -> Location | None:
    """The first and last segment a span touches. Spans in a gap count from the next segment."""
    if not segments:
        return None
    ends = [s.end for s in segments]
    # The first segment that ends after the span starts, then the last one that starts before
    # the span ends.
    i = min(bisect.bisect_right(ends, start), len(segments) - 1)
    starts = [s.start for s in segments]
    j = max(bisect.bisect_left(starts, end) - 1, i)
    return Location(segments[i].kind, segments[i].number, segments[j].number)
