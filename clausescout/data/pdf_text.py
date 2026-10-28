"""Turning the lines of PDF pages into one clean, continuous text that still knows its pages.

PDF text comes out with page furniture mixed into the clauses: running headers and footers,
page numbers, words hyphenated at line ends. Any of these sitting in the middle of a clause
breaks the verbatim grounding check, so I clean them up here before anything else sees the
text. Pages are joined into one string so a clause that runs over a page break reads as one
passage, and I keep each page's character range for citations.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from clausescout.grounding.location import Segment

# Headers and footers live in the first and last few lines of a page.
ZONE = 3
# A line in that zone counts as running furniture if it repeats on this share of pages.
REPEAT_SHARE = 0.4

# "Page 3", "Page 3 of 9" and "- 3 -" are page numbers wherever they sit in the zone.
_LABELLED_PAGE = re.compile(
    r"^(page\s+\d{1,4}(\s*(of|/)\s*\d{1,4})?|[-\u2013\u2014]\s*\d{1,4}\s*[-\u2013\u2014])$",
    re.IGNORECASE,
)
# A bare number could also be a section number, so I only trust it in the checks below.
_BARE_NUMBER = re.compile(r"^\d{1,4}$")


def _key(line: str) -> str:
    # Running headers often differ only by the page number, so I mask digits when comparing.
    return re.sub(r"\d+", "#", " ".join(line.split()).lower())


def _zone(lines: list[str]) -> set[int]:
    # Indexes of the first and last ZONE non-empty lines on a page.
    filled = [i for i, line in enumerate(lines) if line.strip()]
    return set(filled[:ZONE] + filled[-ZONE:])


def _edges(lines: list[str]) -> list[int]:
    # The very first and last non-empty lines, where printed page numbers sit.
    filled = [i for i, line in enumerate(lines) if line.strip()]
    return sorted({filled[0], filled[-1]}) if filled else []


def _bare_page_numbers(pages: list[list[str]]) -> set[tuple[int, int]]:
    """(page, line) positions of bare numbers that count up with the pages.

    Exhibits often start at an arbitrary page number, so I look for one offset between the
    printed number and the page index that most pages share. A "19" that doesn't fit that
    pattern is more likely a section number and stays.
    """
    found = []
    for p, lines in enumerate(pages):
        for i in _edges(lines):
            if _BARE_NUMBER.match(lines[i].strip()):
                found.append((p, i, int(lines[i].strip()) - p))
    offsets = Counter(off for _, _, off in found)
    if not offsets:
        return set()
    offset, n = offsets.most_common(1)[0]
    if n < max(2, math.ceil(REPEAT_SHARE * len(pages))):
        return set()
    return {(p, i) for p, i, off in found if off == offset}


def remove_running_lines(pages: list[list[str]]) -> list[list[str]]:
    """Drops repeated headers and footers and printed page numbers from each page's lines."""
    zones = [_zone(lines) for lines in pages]
    counts = Counter()
    for lines, zone in zip(pages, zones, strict=True):
        # I count each key once per page, so a line repeated on one page doesn't qualify.
        counts.update({_key(lines[i]) for i in zone})
    need = max(2, math.ceil(REPEAT_SHARE * len(pages)))
    # A running line needs at least one letter. Masked bare numbers all look alike ("#"), and
    # page numbers are handled separately so section numbers survive.
    running = {k for k, n in counts.items() if n >= need and re.search(r"[^\W\d_]", k)}
    numbers = _bare_page_numbers(pages)
    seen: set[str] = set()
    cleaned = []
    for p, (lines, zone) in enumerate(zip(pages, zones, strict=True)):
        keep = []
        for i, line in enumerate(lines):
            key = _key(line)
            if i in zone:
                if (p, i) in numbers or _LABELLED_PAGE.match(line.strip()):
                    continue
                # The first time a running line shows up it is often the real title of the
                # contract, so I keep that one and drop the repeats.
                if key in running:
                    if key in seen:
                        continue
                    seen.add(key)
            keep.append(line)
        cleaned.append(keep)
    return cleaned


_LINE_END_HYPHEN = re.compile(r"(\w+)-$")
_LINE_START_WORD = re.compile(r"(\w+)(.*)$", re.DOTALL)
_LETTERS = r"[^\W\d_]+"


def rejoin_hyphenated(pages: list[list[str]]) -> list[list[str]]:
    """Joins words split by a hyphen at the end of a line, including across page breaks.

    A line-end hyphen is either a typesetter's break ("con-" + "tract") or a real hyphen in a
    compound ("non-" + "exclusive"), and dropping it in the second case would change the
    wording. So I check the document itself: if the joined word appears elsewhere without a
    hyphen and the hyphenated form doesn't, I drop the hyphen. Otherwise I keep it and only
    remove the line break. I move just the word fragment up, so page boundaries barely shift.
    """
    pages = [list(lines) for lines in pages]
    text = "\n".join(line for lines in pages for line in lines)
    words = {w.lower() for w in re.findall(_LETTERS, text)}
    compounds = {w.lower() for w in re.findall(rf"{_LETTERS}(?:-{_LETTERS})+", text)}
    flat = [(p, i) for p, lines in enumerate(pages) for i in range(len(lines))]
    for k, (p, i) in enumerate(flat):
        line = pages[p][i].rstrip()
        m = _LINE_END_HYPHEN.search(line)
        if not m:
            continue
        # The continuation is the next non-empty line, which may be on the next page.
        nxt = next(((q, j) for q, j in flat[k + 1:] if pages[q][j].strip()), None)
        if nxt is None:
            continue
        q, j = nxt
        n = _LINE_START_WORD.match(pages[q][j].lstrip())
        if not n:
            continue
        left, frag, rest = m.group(1), n.group(1), n.group(2)
        joined = (left + frag).lower()
        is_break = (left + frag).isalpha() and joined in words
        if is_break and f"{left}-{frag}".lower() not in compounds:
            pages[p][i] = line[:-1] + frag
        else:
            pages[p][i] = line + frag
        pages[q][j] = rest.lstrip()
    return pages


def pages_to_text(pages: list[list[str]]) -> tuple[str, list[Segment]]:
    """Cleans the pages and joins them into one text with a character range per page."""
    pages = rejoin_hyphenated(remove_running_lines(pages))
    parts, segments, pos = [], [], 0
    for number, lines in enumerate(pages, start=1):
        # Every page keeps its real number, even if cleaning left it empty.
        body = "\n".join(line.rstrip() for line in lines).strip()
        segments.append(Segment("page", number, pos, pos + len(body)))
        parts.append(body)
        pos += len(body) + 1
    return "\n".join(parts), segments
