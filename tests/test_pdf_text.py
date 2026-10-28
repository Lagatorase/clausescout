"""Tests for cleaning PDF text: page furniture, hyphenation, odd characters and page breaks."""

import pymupdf

from clausescout.data.documents import load_document
from clausescout.data.pdf_text import (
    clean_characters,
    pages_to_text,
    rejoin_hyphenated,
    remove_running_lines,
)
from clausescout.grounding.location import locate
from clausescout.grounding.verbatim import GroundingIndex

BODIES = ["Supplier shall deliver.", "Buyer shall pay.", "Either party may end it.", "Law."]


def _pages(n: int) -> list[list[str]]:
    # Each page has a running header with the page number, a body line and a footer.
    return [
        [f"ACME CORP - SUPPLY AGREEMENT - Page {i}", BODIES[i - 1], "Confidential", f"{i}"]
        for i in range(1, n + 1)
    ]


def test_running_headers_footers_and_page_numbers_are_removed():
    cleaned = remove_running_lines(_pages(4))
    # The first copy of a running line stays, because it is often the contract's real title.
    assert cleaned[0] == ["ACME CORP - SUPPLY AGREEMENT - Page 1", BODIES[0], "Confidential"]
    assert cleaned[1:] == [[b] for b in BODIES[1:]]


def test_labelled_page_numbers_are_always_removed():
    pages = [["Body one."], ["Body two.", "- 2 -"], ["Body three.", "Page 3 of 9"]]
    cleaned = remove_running_lines(pages)
    assert cleaned == [["Body one."], ["Body two."], ["Body three."]]


def test_bare_numbers_only_count_when_they_follow_the_pages():
    # Pages 12, 13 and 14 of an exhibit: the bottom numbers count up with the pages.
    pages = [[body, str(12 + i)] for i, body in enumerate(BODIES[:3])]
    assert remove_running_lines(pages) == [[body] for body in BODIES[:3]]
    # A lone "19" or "3" at a page edge that doesn't follow the pages is a section number.
    pages = [["Text.", "19"], ["3", "More text."], ["Last text.", "7"]]
    assert remove_running_lines(pages) == pages


def test_lines_that_repeat_outside_the_page_edges_are_kept():
    # The same sentence in the middle of several pages is real text, not a header.
    pages = [["Head A", "x", "y", "z", "Each party shall comply.", "a", "b", "c", "Foot"]] * 3
    cleaned = remove_running_lines([list(p) for p in pages])
    assert all("Each party shall comply." in p for p in cleaned)


def test_page_segments_point_at_each_page_text():
    text, segs = pages_to_text(_pages(3))
    assert [s.number for s in segs] == [1, 2, 3]
    assert text[segs[1].start:segs[1].end] == "Buyer shall pay."


def _pdf(tmp_path, pages: list[str]):
    # A small real PDF, one string of lines per page, written with pymupdf.
    path = tmp_path / "synthetic.pdf"
    pdf = pymupdf.open()
    for body in pages:
        page = pdf.new_page()
        page.insert_text((72, 72), body)
    pdf.save(path)
    return load_document(path)


def test_pdf_with_running_header_grounds_a_clause_across_lines(tmp_path):
    header = "ACME CORP SUPPLY AGREEMENT CONFIDENTIAL"
    doc = _pdf(tmp_path, [
        f"{header}\n1. Supply. Supplier shall supply\nthe Products to Buyer.\n1",
        f"{header}\n2. Term. Two years.\n2",
        f"{header}\n3. Law. Singapore law.\n3",
    ])
    # Only the first copy of the header survives.
    assert doc.text.count(header) == 1
    hit = GroundingIndex(doc.text).find("Supplier shall supply the Products to Buyer.")
    assert locate(doc.segments, *hit).label == "p. 1"


def test_typesetter_hyphen_is_dropped_when_the_word_appears_whole_elsewhere():
    pages = [["This contract binds the parties. The con-", "tract starts today."]]
    assert rejoin_hyphenated(pages) == [["This contract binds the parties. The contract",
                                         "starts today."]]


def test_compound_hyphen_is_kept_when_only_the_line_break_goes():
    # "nonexclusive" never appears whole, so the hyphen is real and stays.
    pages = [["Licensor grants a non-", "exclusive licence."]]
    assert rejoin_hyphenated(pages) == [["Licensor grants a non-exclusive", "licence."]]
    # A compound written with a hyphen elsewhere keeps it, even if the joined form exists too.
    pages = [["a non-exclusive and nonexclusive licence; a non-", "exclusive right"]]
    assert rejoin_hyphenated(pages)[0][0].endswith("a non-exclusive")


def test_hyphen_break_across_a_page_keeps_the_word_on_the_first_page():
    pages = [["The Supplier shall indem-"], ["nify the Buyer.", "Indemnify means pay."]]
    out = rejoin_hyphenated(pages)
    assert out == [["The Supplier shall indemnify"], ["the Buyer.", "Indemnify means pay."]]


def test_number_ranges_and_dashes_on_their_own_are_left_alone_except_the_break():
    pages = [["see Sections 4-", "6 below", "Signed: -", "Name"]]
    assert rejoin_hyphenated(pages) == [["see Sections 4-6", "below", "Signed: -", "Name"]]


def test_nfkc_fixes_ligatures_look_alike_semicolons_and_odd_spaces():
    lig, greek_q, nbsp = chr(0xFB01), chr(0x037E), chr(0x00A0)
    pages = [[f"the {lig}rst Party{greek_q} and{nbsp}the other"]]
    assert clean_characters(pages) == [["the first Party; and the other"]]


def test_soft_hyphens_always_join_and_never_survive():
    soft = chr(0x00AD)
    # A soft hyphen at a line end is a break even if the joined word appears nowhere else.
    text, _ = pages_to_text([[f"the indemni{soft}", f"fication obli{soft}gations"]])
    assert text == "the indemnification\nobligations"


def test_synthetic_pdf_with_header_hyphen_ligature_and_page_split(tmp_path):
    # Three pages with a running header and page numbers. Page 1 ends with a hyphenated word
    # and starts a clause that finishes on page 2; page 2 has a "fi" ligature.
    lig = chr(0xFB01)
    header = "SUPPLY AGREEMENT - CONFIDENTIAL"
    # The wide font clips long lines at the page edge, so I keep every line short.
    bodies = [
        f"{header}\n1. An indemnification claim\nis final.\n2. Liability. In no event\n"
        "shall the Supplier's liability\nexceed the indemni-\n1",
        f"{header}\nfication cap, being the fees\npaid in the {lig}rst year.\n"
        "3. Term. Two years.\n2",
        f"{header}\n4. Law. Singapore law.\n3",
    ]
    path = tmp_path / "msa.pdf"
    pdf = pymupdf.open()
    for body in bodies:
        # The built-in "japan" font keeps the U+FB01 ligature when the PDF is read back.
        pdf.new_page().insert_text((72, 72), body, fontname="japan")
    pdf.save(path)
    doc = load_document(path)
    clause = ("In no event shall the Supplier's liability exceed the indemnification cap, "
              "being the fees paid in the first year.")
    hit = GroundingIndex(doc.text).find(clause)
    assert hit is not None
    assert locate(doc.segments, *hit).label == "pp. 1-2"
    assert doc.text.count(header) == 1
    assert lig not in doc.text
