"""The Singapore evaluation on fake contracts and fake labels in a temporary folder.

Nothing here reads the real Singapore texts or labels, and no model is loaded: the methods are
stubs plus the keyword baseline.
"""

import importlib.util
import json
import math
from pathlib import Path

import pytest

from clausescout.data.cuad import HIGH_STAKES
from clausescout.data.singapore import LABEL_TYPES
from clausescout.extraction import build_method
from clausescout.findings import Finding

ROOT = Path(__file__).resolve().parents[1]

LAW = "This Agreement is governed by the laws of Singapore."
ASSIGN = "Neither party may assign this Agreement without the prior written consent of the other."
SIAC = ("Any dispute shall be referred to and finally resolved by arbitration administered by the "
        "Singapore International Arbitration Centre.")
COURTS = "The parties submit to the exclusive jurisdiction of the courts of Singapore."
PDPA = ("Each party shall comply with the Personal Data Protection Act 2012 in handling "
        "personal data.")
PRIVACY = "Nothing in this Agreement affects the privacy of either party's internal records."

# Three fully labelled contracts and one that is only half done.
TEXTS = {
    "a": "\n\n".join([LAW, ASSIGN, SIAC, PDPA]),
    "b": "\n\n".join([LAW, COURTS]),
    "c": "\n\n".join([ASSIGN, COURTS, PRIVACY]),
    "d": LAW,
}
PRESENT = {
    "a": {"Governing Law": LAW, "Anti-Assignment": ASSIGN, "Arbitration": SIAC,
          "SIAC Arbitration": SIAC, "Data Protection": PDPA},
    "b": {"Governing Law": LAW},
    # "privacy" is in the text, but it isn't a data protection clause.
    "c": {"Anti-Assignment": ASSIGN},
}


def _load_eval():
    spec = importlib.util.spec_from_file_location("eval_singapore",
                                                  ROOT / "scripts" / "eval_singapore.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _labels(cid):
    text, labels = TEXTS[cid], {}
    for t in LABEL_TYPES:
        quote = PRESENT[cid].get(t)
        if quote:
            start = text.index(quote)
            labels[t] = {"status": "present",
                         "spans": [{"start": start, "end": start + len(quote), "text": quote}]}
        else:
            labels[t] = {"status": "absent", "spans": []}
    return {"contract": cid, "labels": labels}


@pytest.fixture
def fake_set(tmp_path):
    text_dir, label_dir = tmp_path / "text", tmp_path / "labels"
    text_dir.mkdir()
    label_dir.mkdir()
    for cid, text in TEXTS.items():
        (text_dir / f"{cid}.txt").write_text(text, encoding="utf-8")
    for cid in PRESENT:
        (label_dir / f"{cid}.json").write_text(json.dumps(_labels(cid)), encoding="utf-8")
    half = _labels("a")
    half["contract"] = "d"
    half["labels"] = {"Governing Law": {"status": "present", "spans": [
        {"start": 0, "end": len(LAW), "text": LAW}]}}
    (label_dir / "d.json").write_text(json.dumps(half), encoding="utf-8")
    return text_dir, label_dir, tmp_path / "runs"


class Oracle:
    """Quotes exactly the labelled clauses, and counts how often it is run."""

    calls = 0

    def extract(self, cid, text):
        Oracle.calls += 1
        return [Finding(cid, t, q, 0.9) for t, q in PRESENT[cid].items() if t in HIGH_STAKES]


class Silent:
    def extract(self, cid, text):
        return []


def test_scores_fake_labels_and_skips_unfinished_contracts(fake_set):
    ev = _load_eval()
    text_dir, label_dir, runs = fake_set
    Oracle.calls = 0
    result = ev.evaluate({"oracle": (Oracle(), 0.5), "silent": (Silent(), 0.5),
                          "keywords": (build_method("keywords"), 0.5)},
                         ["a", "b", "c", "d", "e"], text_dir, label_dir, runs, n_boot=50)
    assert result["n_contracts"] == 3
    assert result["skipped"] == {"d": "1 of 11 types labelled", "e": "not fetched"}

    oracle, silent = result["methods"]["oracle"], result["methods"]["silent"]
    assert oracle["high_stakes_found_f2"] == pytest.approx(1.0)
    assert silent["high_stakes_found_f2"] == pytest.approx(0.0)
    lo, hi = oracle["high_stakes_found_f2_ci"]
    assert lo <= 1.0 <= hi + 1e-9
    assert oracle["per_type"]["Anti-Assignment"] == {
        "present": 2, "predicted": 2, "tp": 2, "fp": 0, "fn": 0, "found": 2, "precision": 1.0,
        "recall": 1.0, "found_recall": 1.0, "found_f2": 1.0}
    # Types no contract has stay in the table, with nothing to find.
    assert oracle["per_type"]["Non-Compete"]["present"] == 0
    assert math.isnan(oracle["per_type"]["Non-Compete"]["found_recall"])
    assert 0 <= result["methods"]["keywords"]["high_stakes_found_f2"] <= 1


def test_playbook_rules_against_the_labels(fake_set):
    ev = _load_eval()
    text_dir, label_dir, runs = fake_set
    result = ev.evaluate({"silent": (Silent(), 0.5)}, ["a", "b", "c"], text_dir, label_dir,
                         runs, n_boot=0)
    rules = result["methods"]["silent"]["playbook"]
    # No arbitration in b and c: the rule flags both, and both labels agree.
    assert rules["no-arbitration"] == {"tp": 2, "fp": 0, "fn": 0, "tn": 1,
                                       "precision": 1.0, "recall": 1.0}
    # The only arbitration (a) is SIAC, so this rule should never fire.
    assert rules["arbitration-not-siac"]["tp"] + rules["arbitration-not-siac"]["fp"] == 0
    assert math.isnan(rules["arbitration-not-siac"]["precision"])
    # c says "privacy" without a data clause: the text rule stays quiet, so that's a miss.
    assert rules["no-data-protection"] == {"tp": 1, "fp": 0, "fn": 1, "tn": 1,
                                           "precision": 1.0, "recall": 0.5}
    assert result["playbook_present"] == {"Arbitration": 1, "SIAC Arbitration": 1,
                                          "Data Protection": 1}


def test_saved_output_is_reused_and_the_report_is_written(fake_set, tmp_path):
    ev = _load_eval()
    text_dir, label_dir, runs = fake_set
    Oracle.calls = 0
    first = ev.evaluate({"oracle": (Oracle(), 0.5)}, ["a", "b", "c"], text_dir, label_dir, runs,
                        n_boot=0)
    assert Oracle.calls == 3
    # A second run reads runs/<method>/partial.jsonl and never builds the method.
    built = []
    again = ev.evaluate({"oracle": (lambda: built.append(1) or Oracle(), 0.5)},
                        ["a", "b", "c"], text_dir, label_dir, runs, n_boot=0)
    assert built == [] and Oracle.calls == 3
    assert again["methods"] == first["methods"]

    report = tmp_path / "report.md"
    ev.write_report(again, report)
    text = report.read_text(encoding="utf-8")
    assert "| oracle | 0.5 | 1.000 |" in text and "no-data-protection" in text


def test_nothing_labelled_stops_with_a_clear_message(tmp_path):
    ev = _load_eval()
    with pytest.raises(SystemExit, match="label_tool"):
        ev.evaluate({}, ["a"], tmp_path, tmp_path, tmp_path / "runs", n_boot=0)
