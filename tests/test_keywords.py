"""Tests for the sentence splitter and the keyword baseline on a small made-up contract."""

from clausescout.extraction.keywords import KeywordExtractor
from clausescout.extraction.sentences import sentences

CONTRACT = """DISTRIBUTION AGREEMENT

This Distribution Agreement is made on March 3, 2020 by and between Acme Inc. ("Acme") and
Beta Pte. Ltd. ("Distributor").

2.1. Acme hereby grants Distributor a non-exclusive, non-transferable licence to use the
Marks. Acme shall not increase prices during the Term.

9. Assignment. Neither party may assign this Agreement without the prior written consent of
the other party.

12. Governing Law. This Agreement shall be governed by the laws of Singapore.
"""


def test_sentences_skip_abbreviations_and_section_numbers():
    spans = [CONTRACT[a:b] for a, b in sentences(CONTRACT)]
    assert "DISTRIBUTION AGREEMENT" in spans
    # "Acme Inc." and "Pte. Ltd." don't end the sentence.
    assert any(s.startswith("This Distribution Agreement") and s.endswith('("Distributor").')
               for s in spans)
    # "2.1." is a section number, not a sentence of its own.
    assert any(s.startswith("2.1. Acme hereby grants") for s in spans)
    assert "Acme shall not increase prices during the Term." in spans


def test_long_passages_are_cut():
    text = "word " * 1000
    assert all(b - a <= 300 for a, b in sentences(text, max_chars=300))


def test_keyword_findings_cover_the_obvious_clauses():
    findings = KeywordExtractor().extract("c1", CONTRACT)
    by_cat = {}
    for f in findings:
        by_cat.setdefault(f.category, []).append(f)
    assert by_cat["Document Name"][0].text == "DISTRIBUTION AGREEMENT"
    assert by_cat["Agreement Date"][0].text == "March 3, 2020"
    assert "by and between" in by_cat["Parties"][0].text
    assert any("governed by the laws of Singapore" in f.text for f in by_cat["Governing Law"])
    assert any("prior written consent" in f.text for f in by_cat["Anti-Assignment"])
    assert "Non-Transferable License" in by_cat and "License Grant" in by_cat
    assert "Price Restrictions" in by_cat
    # "non-exclusive" must not count as an exclusivity clause.
    assert "Exclusivity" not in by_cat
    # Every finding is real contract text at its own offsets, with a score in (0, 1].
    for f in findings:
        assert CONTRACT[f.start:f.end] == f.text and 0 < f.score <= 1


def test_more_matching_patterns_mean_a_higher_score():
    one = KeywordExtractor().extract("a", "The Licensee may audit the records.")
    two = KeywordExtractor().extract("b", "The Licensee may audit and inspect the books.")
    s1 = max(f.score for f in one if f.category == "Audit Rights")
    s2 = max(f.score for f in two if f.category == "Audit Rights")
    assert s2 > s1
