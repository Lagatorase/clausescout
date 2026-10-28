"""Hand-made cases for the contract-level (clause present or not) metrics."""

import math

import pytest

from clausescout.metrics.contract import contract_metrics

GL = "Governing Law"
CAP = "Cap On Liability"


def _case():
    # Four contracts. Governing Law is in A, B and C; Cap On Liability only in A.
    gold = {
        ("A", GL): ["governed by the laws of New York"],
        ("B", GL): ["laws of the State of Delaware"],
        ("C", GL): ["laws of England and Wales"],
        ("D", GL): [],
        ("A", CAP): ["in no event shall liability exceed the fees paid"],
        ("B", CAP): [],
        ("C", CAP): [],
        ("D", CAP): [],
    }
    preds = {
        # A: right clause, right span.
        ("A", GL): [("governed by the laws of New York", 0.9)],
        # B: says present, but quotes the wrong text.
        ("B", GL): [("this agreement may be signed in counterparts", 0.8)],
        # C: below the threshold, so a miss.
        ("C", GL): [("laws of England and Wales", 0.2)],
        # D: a false alarm.
        ("D", GL): [("the parties agree", 0.6)],
        ("A", CAP): [("in no event shall liability exceed the fees paid", 0.7)],
    }
    return gold, preds


def test_presence_precision_recall_f1_per_category():
    gold, preds = _case()
    m = contract_metrics(gold, preds, threshold=0.5)
    gl = m.per_category[GL]
    # Predicted present: A, B, D. Gold present: A, B, C. So TP 2, FP 1, FN 1.
    assert (gl.tp, gl.fp, gl.fn, gl.tn) == (2, 1, 1, 0)
    assert gl.precision == pytest.approx(2 / 3)
    assert gl.recall == pytest.approx(2 / 3)
    assert gl.f1 == pytest.approx(2 / 3)
    # Of the two true positives only A quoted a matching span.
    assert gl.span_correct == pytest.approx(1 / 2)
    # Found with a correct span: 1 of the 3 contracts that have the clause.
    assert gl.found_recall == pytest.approx(1 / 3)
    cap = m.per_category[CAP]
    assert (cap.tp, cap.fp, cap.fn, cap.tn) == (1, 0, 0, 3)
    assert cap.f1 == 1.0


def test_f2_weights_recall_more_than_precision():
    gold, preds = _case()
    gl = contract_metrics(gold, preds, threshold=0.5).per_category[GL]
    p, r = gl.precision, gl.recall
    assert gl.f2 == pytest.approx(5 * p * r / (4 * p + r))


def test_lower_threshold_trades_precision_for_recall():
    gold, preds = _case()
    gl = contract_metrics(gold, preds, threshold=0.1).per_category[GL]
    assert gl.recall == 1.0
    assert gl.precision == pytest.approx(3 / 4)


def test_per_category_thresholds():
    gold, preds = _case()
    m = contract_metrics(gold, preds, threshold={GL: 0.1, CAP: 0.95})
    assert m.per_category[GL].recall == 1.0
    assert m.per_category[CAP].recall == 0.0


def test_micro_and_macro_averages():
    gold, preds = _case()
    m = contract_metrics(gold, preds, threshold=0.5)
    # Micro pools both categories: TP 3, FP 1, FN 1.
    assert m.micro.precision == pytest.approx(3 / 4)
    assert m.micro.recall == pytest.approx(3 / 4)
    # Macro averages the per-category F1 values: (2/3 + 1) / 2.
    assert m.macro["f1"] == pytest.approx((2 / 3 + 1) / 2)


def test_high_stakes_summary_only_uses_high_stakes_types():
    gold, preds = _case()
    gold[("A", "Parties")] = ["Acme Inc."]
    preds[("A", "Parties")] = [("Acme Inc.", 0.9)]
    m = contract_metrics(gold, preds, threshold=0.5)
    # Governing Law and Cap On Liability are high-stakes, Parties is not.
    assert m.high_stakes["recall"] == pytest.approx((2 / 3 + 1) / 2)


def test_undefined_scores_are_nan_not_zero():
    # No gold and no predictions: precision and recall are undefined, not 0 or 1.
    gold = {("A", GL): []}
    gl = contract_metrics(gold, {}, threshold=0.5).per_category[GL]
    assert math.isnan(gl.precision) and math.isnan(gl.recall)
    assert gl.tn == 1


def test_bootstrap_interval_contains_point_estimate():
    gold, preds = _case()
    g2, p2 = {}, {}
    for k in range(10):
        for (cid, cat), v in gold.items():
            g2[(f"{cid}{k}", cat)] = v
            if (cid, cat) in preds:
                p2[(f"{cid}{k}", cat)] = preds[(cid, cat)]
    m = contract_metrics(g2, p2, threshold=0.5, n_boot=200, seed=0)
    lo, hi = m.per_category[GL].ci["f1"]
    assert lo <= m.per_category[GL].f1 <= hi
    assert "recall" in m.micro.ci
    # The high-stakes mean gets its own interval, which the selection rule compares.
    lo, hi = m.high_stakes_ci["f2"]
    assert lo <= m.high_stakes["f2"] <= hi
