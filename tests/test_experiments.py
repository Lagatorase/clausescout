"""The experiment runner on tiny synthetic contracts with a stub method (no dataset needed)."""

import json

from clausescout.data.cuad import CATEGORIES, Contract, Span
from clausescout.experiments import run_experiment
from clausescout.findings import Finding

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
