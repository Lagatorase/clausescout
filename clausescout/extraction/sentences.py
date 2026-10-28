"""Splitting contract text into sentence-sized passages with character offsets.

The keyword baseline returns whole sentences, because CUAD's gold spans are mostly a sentence
or a clause long. Contracts are full of abbreviations ("Inc.", "U.S.", "Section 2.1."), so a
plain split on full stops would cut them in the wrong places.
"""

from __future__ import annotations

import re

# Words that end with a full stop without ending the sentence.
_ABBREVIATIONS = {
    "inc", "ltd", "pte", "pty", "bhd", "sdn", "gmbh", "co", "corp", "llc", "l.l.c", "l.p", "lp",
    "plc", "n.v", "b.v", "s.a", "a.g",
    "no", "nos", "sec", "secs", "art", "arts", "para", "cl", "ch", "vol", "pp", "p",
    "mr", "mrs", "ms", "dr", "st", "jr", "sr", "u.s", "u.k", "e.g", "i.e", "etc", "viz", "vs",
    "approx", "dept", "est", "fig", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep",
    "sept", "oct", "nov", "dec",
}
# A candidate break: a full stop, then whitespace, then something that can start a sentence.
_CANDIDATE = re.compile(r"\.(?=\s+[\"'(\[]?[A-Z0-9])")
_BLANK_LINE = re.compile(r"\n[ \t\r\f\v]*\n")


def _is_abbreviation(text: str, dot: int) -> bool:
    # The word just before the full stop, e.g. "Inc" in "Acme Inc. shall".
    start = dot
    while start > 0 and not text[start - 1].isspace() and text[start - 1] not in "(\"'":
        start -= 1
    word = text[start:dot].lower()
    if word in _ABBREVIATIONS:
        return True
    # Single letters ("A. Smith") and section numbers ("2.1.") are not sentence ends.
    return len(word) == 1 or bool(re.fullmatch(r"[\d.]+", word))


def sentences(text: str, max_chars: int = 2000) -> list[tuple[int, int]]:
    """(start, end) offsets of sentence-like passages, trimmed of surrounding whitespace.

    Blank lines always end a passage. Very long passages (tables, run-on recitals) are cut
    at max_chars so one match doesn't return half a page.
    """
    breaks = {0, len(text)}
    for m in _BLANK_LINE.finditer(text):
        breaks.update((m.start(), m.end()))
    for m in _CANDIDATE.finditer(text):
        if not _is_abbreviation(text, m.start()):
            breaks.add(m.end())
    out = []
    points = sorted(breaks)
    for a, b in zip(points, points[1:], strict=False):
        # I trim whitespace so each passage starts and ends on real text.
        while a < b and text[a].isspace():
            a += 1
        while b > a and text[b - 1].isspace():
            b -= 1
        while b - a > max_chars:
            out.append((a, a + max_chars))
            a += max_chars
        if b > a:
            out.append((a, b))
    return out
