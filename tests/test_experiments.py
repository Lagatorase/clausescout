"""The experiment runner on tiny synthetic contracts with a stub method (no dataset needed)."""

import json

from clausescout.data.cuad import CATEGORIES, Contract, Span
from clausescout.experiments import run_experiment, score_findings
from clausescout.findings import Finding, top_per_type

LAW = "This Agreement is governed by the laws of Singapore."


def _contract(cid: str, with_law: bool) -> Contract:
    text = f"SUPPLY AGREEMENT\n\n1. Supply. Goods.\n\n{LAW if with_law else 'No law clause.'}"
    c = Contract(cid, text, {cat: [] for cat in CATEGORIES})
    if with_law:
        c.labels["Governing Law"] = [Span(LAW, text.index(LAW))]
    return c


class StubMethod:
    """Quotes the law clause correctly, and also invents one clause that isn't there."""

    name = "stub"

    def __init__(self):
        self.usage = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}

    def extract(self, contract_id, text):
        self.usage["input_tokens"] += 100
        self.usage["cost_usd"] += 0.01
        out = [Finding(contract_id, "Cap On Liability", "Liability is capped at USD 1.", 0.9)]
        if LAW in text:
            out.append(Finding(contract_id, "Governing Law", LAW.replace(" ", "  "), 0.8))
        return out


def test_runner_grounds_scores_and_accounts_for_cost():
    contracts = [_contract("a", True), _contract("b", False), _contract("c", True)]
    summary, findings = run_experiment(StubMethod(), contracts, threshold=0.5)
    # Two real quotes survive; the three invented ones are rejected and counted.
    assert len(findings) == 2 and all(f.category == "Governing Law" for f in findings)
    assert summary["grounding"]["rejected"] == 3
    assert summary["grounding"]["rejection_rate"] == 3 / 5
    gl = summary["per_category"]["Governing Law"]
    assert gl["contract"]["recall"] == 1.0 and gl["contract"]["precision"] == 1.0
    assert gl["span"]["aupr"] == 1.0
    assert summary["cost_per_contract_usd"] == 0.01
    assert summary["time"]["per_contract_s"] >= 0
    # The summary has to be saveable as JSON.
    json.dumps(summary, default=float)


def test_interrupted_run_resumes_without_redoing_contracts(tmp_path):
    contracts = [_contract("a", True), _contract("b", False), _contract("c", True)]
    resume = tmp_path / "partial.jsonl"
    # The first run gets through two contracts before it is stopped.
    run_experiment(StubMethod(), contracts[:2], threshold=0.5, resume_path=resume)
    assert len(resume.read_text().splitlines()) == 2

    fresh = StubMethod()
    summary, findings = run_experiment(fresh, contracts, threshold=0.5, resume_path=resume)
    # Only the third contract is extracted again, but usage and results cover all three.
    assert fresh.usage["input_tokens"] == 100
    assert summary["usage"]["input_tokens"] == 300
    full, _ = run_experiment(StubMethod(), contracts, threshold=0.5)
    assert summary["span"] == full["span"] and summary["grounding"] == full["grounding"]


def test_cap_keeps_the_best_distinct_quotes_per_clause_type():
    fs = [Finding("c1", "Governing Law", "a", 0.2, start=5),
          Finding("c1", "Governing Law", "b", 0.9, start=9),
          Finding("c1", "Governing Law", "b", 0.95, start=9),  # repeat, counted once
          Finding("c1", "Governing Law", "c", 0.5, start=1),
          Finding("c1", "Exclusivity", "d", 0.1),
          Finding("c2", "Governing Law", "e", 0.3)]
    kept = top_per_type(fs, 2)
    got = sorted((f.contract_id, f.category, f.text, f.score) for f in kept)
    assert got == [("c1", "Exclusivity", "d", 0.1), ("c1", "Governing Law", "b", 0.95),
                   ("c1", "Governing Law", "c", 0.5), ("c2", "Governing Law", "e", 0.3)]
    assert len(top_per_type(fs, None)) == len(fs)


def test_capped_scoring_hides_a_correct_quote_ranked_third():
    # The correct law quote is only the third best, so with a cap of 2 the reviewer never sees
    # it: presence still counts, but found F2 drops to 0. Span metrics ignore the cap.
    c = _contract("c1", with_law=True)
    fs = [Finding("c1", "Governing Law", "SUPPLY AGREEMENT", 0.9),
          Finding("c1", "Governing Law", "1. Supply. Goods.", 0.8),
          Finding("c1", "Governing Law", LAW, 0.7)]
    capped = score_findings([c], fs, threshold=0.5, max_per_type=2)
    uncapped = score_findings([c], fs, threshold=0.5, max_per_type=None)
    law_c = capped["per_category"]["Governing Law"]["contract"]
    law_u = uncapped["per_category"]["Governing Law"]["contract"]
    assert law_c["recall"] == law_u["recall"] == 1.0
    assert law_c["found_f2"] == 0.0 and law_u["found_f2"] == 1.0
    assert capped["span"] == uncapped["span"]
    assert capped["findings_per_contract"] == 2 and uncapped["findings_per_contract"] == 3


def test_run_pauses_while_memory_is_low(monkeypatch):
    import clausescout.experiments as ex

    # Free RAM reads low twice, then recovers; the run should wait, not fail or skip.
    readings = iter([0.5, 0.8, 3.0])
    monkeypatch.setattr(ex, "memory_gb", lambda: (16.0, next(readings, 3.0)))
    monkeypatch.setattr(ex.time, "sleep", lambda s: None)
    summary, _ = run_experiment(StubMethod(), [_contract("c1", True)], min_free_gb=1.5)
    assert summary["time"]["paused_for_memory_s"] == 60
    assert summary["contracts"] == 1
