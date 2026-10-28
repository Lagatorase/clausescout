"""The LLM method with a stub client: chunking, merging, bad replies and hosted-mode safety."""

import pytest

from clausescout.data.cuad import CATEGORIES, Contract, Span
from clausescout.experiments import run_experiment
from clausescout.llm.client import StubClient, build_client
from clausescout.llm.extractor import LLMExtractor, chunks, response_schema

LAW = "This Agreement is governed by the laws of Singapore."


def test_chunks_overlap_and_cover_the_text():
    text = "".join(f"Line {i} of the contract.\n" for i in range(400))
    parts = chunks(text, size=1000, overlap=200)
    assert parts[0][0] == 0 and parts[-1][1] == len(text)
    for (a1, b1), (a2, _) in zip(parts, parts[1:], strict=False):
        assert a2 < b1, "neighbouring chunks overlap"
        assert a2 > a1, "chunks always move forward"
        assert text[b1 - 1] == "\n" and text[a2 - 1] == "\n", "cuts fall on line breaks"


def test_system_prompt_lists_every_type_and_schema_restricts_types():
    ex = LLMExtractor(StubClient([]))
    for cat in CATEGORIES:
        assert f"- {cat}: " in ex.system
    assert response_schema(["Parties"])["properties"]["clauses"]["items"]["properties"][
        "type"]["enum"] == ["Parties"]


def test_duplicates_from_overlapping_chunks_merge_and_keep_the_higher_confidence():
    text = "A" * 50 + "\n" + LAW + "\n" + "B" * 50
    replies = [
        {"clauses": [{"type": "Governing Law", "quote": LAW, "confidence": "medium"}]},
        {"clauses": [{"type": "Governing Law", "quote": " " + LAW, "confidence": "high"},
                     {"type": "Made Up Type", "quote": LAW, "confidence": "high"}]},
    ]
    ex = LLMExtractor(StubClient(replies), chunk_chars=80, overlap_chars=60)
    found = ex.extract("c", text)
    assert len(found) == 1 and found[0].score == 0.9
    assert ex.usage["unknown_type"] == 1 and ex.usage["calls"] >= 2


def test_broken_json_is_counted_not_hidden():
    ex = LLMExtractor(StubClient(["not json at all"]))
    assert ex.extract("c", LAW) == []
    assert ex.usage["bad_json"] == 1


def test_invented_quotes_are_rejected_by_the_runner():
    c = Contract("c", f"SUPPLY AGREEMENT\n\n{LAW}", {cat: [] for cat in CATEGORIES})
    c.labels["Governing Law"] = [Span(LAW, c.text.index(LAW))]
    replies = [{"clauses": [
        {"type": "Governing Law", "quote": LAW, "confidence": "high"},
        {"type": "Cap On Liability", "quote": "Liability is capped at the fees paid.",
         "confidence": "high"},
    ]}]
    summary, kept = run_experiment(LLMExtractor(StubClient(replies)), [c])
    assert [f.category for f in kept] == ["Governing Law"]
    assert summary["grounding"]["rejected"] == 1


def test_hosted_backends_need_explicit_permission(monkeypatch):
    monkeypatch.setenv("ALLOW_HOSTED_LLM", "false")
    with pytest.raises(RuntimeError, match="ALLOW_HOSTED_LLM"):
        build_client("anthropic")
