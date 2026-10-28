"""The hybrid method with stub candidates and a stub LLM."""

from clausescout.findings import Finding
from clausescout.llm.client import StubClient
from clausescout.llm.hybrid import HybridExtractor

TEXT = ("Neither party may assign this Agreement without consent. "
        "This Agreement is governed by the laws of Singapore.")
ASSIGN = (0, TEXT.index(" This"))
LAW = (TEXT.index("This"), len(TEXT))


class StubQA:
    def extract(self, contract_id, text):
        return [
            Finding(contract_id, "Anti-Assignment", text[slice(*ASSIGN)], 0.6, *ASSIGN),
            Finding(contract_id, "Change Of Control", text[slice(*ASSIGN)], 0.4, *ASSIGN),
            Finding(contract_id, "Governing Law", text[slice(*LAW)], 0.3, *LAW),
            Finding(contract_id, "Parties", "too weak", 0.01, 0, 8),
        ]


def _scores(found):
    return {(f.category, f.start): round(f.score, 3) for f in found}


def test_llm_confirms_rejects_and_adds_types():
    # Passages are sent strongest first: the assignment span (0.6), then the law span (0.3).
    reply = {"passages": [{"id": 0, "types": ["Anti-Assignment"]},
                          {"id": 1, "types": ["Governing Law", "Third Party Beneficiary"]}]}
    client = StubClient([reply])
    ex = HybridExtractor(client, StubQA())
    s = _scores(ex.extract("c", TEXT))
    assert s[("Anti-Assignment", 0)] == 0.8          # confirmed: 0.5 + 0.5 * 0.6
    assert s[("Change Of Control", 0)] == 0.08       # rejected: 0.2 * 0.4
    assert s[("Governing Law", LAW[0])] == 0.65      # confirmed: 0.5 + 0.5 * 0.3
    assert s[("Third Party Beneficiary", LAW[0])] == 0.5  # added by the LLM
    # The 0.01 candidate is below min_prob, so it never reaches the LLM.
    assert ex.usage["passages"] == 2 and len(client.calls) == 1
    assert "suggested: Anti-Assignment, Change Of Control" in client.calls[0][1]


def test_skipped_passages_and_broken_replies_keep_qa_scores():
    ex = HybridExtractor(StubClient(["{broken"]), StubQA())
    s = _scores(ex.extract("c", TEXT))
    assert s[("Anti-Assignment", 0)] == 0.6 and s[("Governing Law", LAW[0])] == 0.3
    assert ex.usage["bad_json"] == 1


def test_every_hybrid_quote_is_exact_contract_text():
    reply = {"passages": [{"id": 0, "types": ["Anti-Assignment"]}, {"id": 1, "types": []}]}
    for f in HybridExtractor(StubClient([reply]), StubQA()).extract("c", TEXT):
        assert TEXT[f.start:f.end] == f.text
