"""The playbook engine on made-up findings."""

from clausescout.findings import Finding
from clausescout.playbook.engine import apply_playbook, load_playbook

RULES = load_playbook()


def _ids(findings, text="Disputes go to SIAC arbitration. Personal data is protected."):
    return [f.rule.id for f in apply_playbook(RULES, findings, text)]


def F(cat, text):
    return Finding("c", cat, text, 0.9, 0, len(text))


def test_default_playbook_loads_and_marks_unmeasured_rules():
    by_id = {r.id: r for r in RULES}
    assert by_id["uncapped-liability"].measurable
    assert by_id["exclusivity-no-end"].measurable
    assert not by_id["no-arbitration"].measurable
    assert not by_id["arbitration-not-siac"].measurable


def test_presence_absence_and_quote_rules():
    findings = [
        F("Uncapped Liability", "Liability for breach of confidentiality is unlimited."),
        F("Exclusivity", "Supplier shall sell only to Buyer."),
        F("Non-Compete", "Distributor shall not compete for two (2) years after termination."),
        F("Change Of Control", "Either party may terminate upon a change of control."),
        F("Governing Law", "This Agreement is governed by the laws of New York."),
    ]
    ids = _ids(findings)
    assert "uncapped-liability" in ids and "no-liability-cap" in ids
    assert "exclusivity-no-end" in ids
    assert "non-compete-no-end" not in ids  # it has a duration
    assert "change-of-control-termination" in ids
    assert "governing-law-not-singapore" in ids and "no-governing-law" not in ids
    # Most severe flags come first.
    severities = [f.rule.severity for f in apply_playbook(RULES, findings, "arbitrat SIAC data")]
    assert severities == sorted(severities, key=["high", "medium", "low"].index)


def test_quote_lacks_needs_the_clause_to_exist():
    assert "exclusivity-no-end" not in _ids([])
    assert "no-governing-law" in _ids([])


def test_text_rules():
    assert "no-arbitration" in _ids([], text="Courts of New York.")
    assert "arbitration-not-siac" in _ids([], text="Disputes go to ICC arbitration.")
    assert "arbitration-not-siac" not in _ids([], text="Disputes go to SIAC arbitration.")
    assert "no-data-protection" in _ids([], text="Nothing about that here.")


def test_evidence_points_at_the_quotes():
    cap = F("Change Of Control", "Either party may terminate upon a change of control.")
    flag = next(f for f in apply_playbook(RULES, [cap], "") if f.rule.id.startswith("change"))
    assert flag.evidence == [cap]
