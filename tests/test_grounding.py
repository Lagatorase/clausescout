"""Tests for the verbatim grounding check."""

from clausescout.findings import Finding
from clausescout.grounding.verbatim import GroundingIndex, ground_findings, normalise

CONTRACT = (
    "1.  Term.\n\nThis Agreement shall commence on the \u201cEffective Date\u201d and\n"
    "continue for two (2) years.\n\n"
    "2. Governing Law. This Agreement is governed by the laws of the State of New York.\n\n"
    "3. Notices. Notices under this Agreement go to the Company\u2019s office.\n\n"
    "9. Governing Law. This Agreement is governed by the laws of the State of New York."
)


def test_normalise_only_touches_whitespace_and_quotes():
    assert normalise("  a\n\tb\u00a0 c ") == "a b c"
    assert normalise("\u201cX\u201d and \u2018y\u2019") == "\"X\" and 'y'"
    # Dashes, case and punctuation are left alone.
    assert normalise("Non\u2014Compete, LLC") == "Non\u2014Compete, LLC"


def test_exact_quote_is_found_with_original_offsets():
    idx = GroundingIndex(CONTRACT)
    quote = "governed by the laws of the State of New York"
    start, end = idx.find(quote)
    assert CONTRACT[start:end] == quote


def test_quote_with_different_whitespace_and_straight_quotes_maps_back_to_original_text():
    idx = GroundingIndex(CONTRACT)
    # The model flattened the line break and used straight quotes.
    start, end = idx.find('commence on the "Effective Date" and continue for two (2) years.')
    original = CONTRACT[start:end]
    assert original.startswith("commence on the \u201cEffective Date\u201d and\ncontinue")
    assert original.endswith("years.")


def test_paraphrase_case_change_and_invented_text_are_rejected():
    idx = GroundingIndex(CONTRACT)
    assert idx.find("governed by the law of the State of New York") is None
    assert idx.find("Governed By The Laws Of The State Of New York") is None
    assert idx.find("This Agreement may be terminated for convenience") is None
    assert idx.find("   ") is None
    assert idx.find("") is None


def test_hint_picks_the_nearest_of_several_occurrences():
    idx = GroundingIndex(CONTRACT)
    quote = "This Agreement is governed by the laws of the State of New York."
    first = idx.find(quote)
    last = idx.find(quote, hint=len(CONTRACT))
    assert first[0] < last[0]
    assert CONTRACT[last[0]:last[1]] == quote


def test_ground_findings_keeps_grounded_ones_and_counts_rejections():
    findings = [
        Finding("c1", "Governing Law", "governed by the laws of the State of New York", 0.9),
        Finding("c1", "Termination For Convenience", "either party may terminate at will"),
        Finding("c1", "Notices", "go to the Company's office"),
    ]
    kept, stats = ground_findings(findings, CONTRACT)
    assert [f.category for f in kept] == ["Governing Law", "Notices"]
    # The kept text is the exact contract text, so the curly apostrophe comes back.
    assert kept[1].text == "go to the Company\u2019s office"
    assert CONTRACT[kept[1].start:kept[1].end] == kept[1].text
    assert (stats.submitted, stats.accepted, stats.rejected) == (3, 2, 1)
    assert stats.rejection_rate == 1 / 3
    assert stats.rejected_examples[0].category == "Termination For Convenience"


def test_stats_add_up_across_contracts():
    _, s1 = ground_findings([Finding("a", "Parties", "nope")], CONTRACT)
    _, s2 = ground_findings([Finding("b", "Parties", "Term.")], CONTRACT)
    total = s1 + s2
    assert (total.submitted, total.rejected) == (2, 1)
    assert total.rejection_rate == 0.5
