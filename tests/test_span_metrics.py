"""Hand-made cases for the CUAD span-level metrics, where I can work out the answer on paper."""

import math

import pytest

from clausescout.metrics.span import (
    CONF_THRESHOLDS,
    is_match,
    jaccard,
    pr_curve,
    span_metrics,
)


def test_jaccard_strips_only_cuad_punctuation_and_lowercases():
    # The official code removes . , ; : and splits on single spaces after lowercasing.
    assert jaccard("This Agreement.", "this agreement") == 1.0
    assert jaccard("a b c d", "a b") == 0.5
    # Brackets are not stripped, so "(a)" and "a" are different words.
    assert jaccard("(a) b", "a b") == pytest.approx(1 / 3)
    # A slash becomes a space.
    assert jaccard("and/or", "and or") == 1.0


def test_match_needs_half_overlap_and_parties_allow_substring():
    assert is_match("the quick brown fox", "the quick brown", "Governing Law")
    # Exactly 0.5 counts as a match, just below does not.
    assert is_match("a b c d", "a b", "Governing Law")
    assert not is_match("a b c d e", "a b", "Governing Law")
    # For Parties, a gold span inside a longer prediction counts even with low overlap.
    long_pred = "Acme Inc. a Delaware corporation with offices at 1 Main Street"
    assert not is_match("Acme Inc.", long_pred, "Governing Law")
    assert is_match("Acme Inc.", long_pred, "Parties")


def test_thresholds_match_the_official_grid():
    # 0.99 down to 0.01 in steps of 0.01, then 0.001 and 0.
    assert len(CONF_THRESHOLDS) == 101
    assert CONF_THRESHOLDS[0] == pytest.approx(0.99)
    assert CONF_THRESHOLDS[-3] == pytest.approx(0.01)
    assert CONF_THRESHOLDS[-2:] == [0.001, 0]


def _gold_and_preds():
    # Two contracts, one category. Contract A has two gold spans, contract B has none.
    gold = {
        ("A", "Governing Law"): ["governed by the laws of New York", "venue in New York County"],
        ("B", "Governing Law"): [],
    }
    preds = {
        # A strong correct hit, a weaker correct hit on the second span, and a weak miss.
        ("A", "Governing Law"): [
            ("governed by the laws of New York", 0.9),
            ("venue in New York County", 0.5),
            ("the parties agree as follows", 0.3),
        ],
        # A confident false positive on a contract with no such clause.
        ("B", "Governing Law"): [("this agreement is binding", 0.7)],
    }
    return gold, preds


def test_pr_curve_counts_tp_fp_fn_like_the_official_code():
    gold, preds = _gold_and_preds()
    curve = pr_curve(gold, preds)
    by_conf = dict(zip(curve.confs, zip(curve.precisions[1:], curve.recalls[1:], strict=True),
                       strict=True))
    # Above 0.9 nothing is predicted, so precision is undefined and recall is 0.
    p, r = by_conf[CONF_THRESHOLDS[0]]
    assert math.isnan(p) and r == 0
    # At 0.8 only the 0.9 hit survives: 1 TP, 0 FP, 1 FN.
    p, r = by_conf[CONF_THRESHOLDS[19]]
    assert (p, r) == (1.0, 0.5)
    # At 0.6 the 0.7 false positive joins: 1 TP, 1 FP.
    p, r = by_conf[CONF_THRESHOLDS[39]]
    assert (p, r) == (0.5, 0.5)
    # At 0.4 the second span is found: 2 TP, 1 FP.
    p, r = by_conf[CONF_THRESHOLDS[59]]
    assert p == pytest.approx(2 / 3) and r == 1.0
    # At 0 everything is in: 2 TP, 2 FP.
    p, r = by_conf[0]
    assert (p, r) == (0.5, 1.0)


def test_aupr_and_precision_at_recall_on_a_known_curve():
    gold, preds = _gold_and_preds()
    m = span_metrics(gold, preds)
    # After the official smoothing (best precision at this recall or higher), the curve is
    # 1.0 from recall 0 to 0.5, drops straight down to 2/3 at recall 0.5, then stays at 2/3
    # up to recall 1. So the area is 0.5 * 1 + 0.5 * 2/3.
    assert m.overall.aupr == pytest.approx(0.5 + 0.5 * 2 / 3)
    assert m.overall.prec_at_80 == pytest.approx(2 / 3)
    assert m.overall.prec_at_90 == pytest.approx(2 / 3)


def test_precision_at_recall_ignores_the_conf_zero_point_like_the_official_code():
    # The only way to reach full recall is the 0.0005 prediction, which only shows up at conf 0.
    # The official code zips with the confidence list, which drops that last point, so
    # precision at 80% recall is 0 here even though conf 0 would reach it.
    gold = {("A", "Governing Law"): ["laws of New York"]}
    preds = {("A", "Governing Law"): [("laws of New York", 0.0005)]}
    m = span_metrics(gold, preds)
    assert m.overall.prec_at_80 == 0.0
    # AUPR still uses the conf 0 point.
    assert m.overall.aupr > 0


def test_perfect_and_empty_predictions():
    gold = {("A", "Parties"): ["Acme Inc."], ("A", "Governing Law"): []}
    perfect = {("A", "Parties"): [("Acme Inc.", 0.99)], ("A", "Governing Law"): []}
    m = span_metrics(gold, perfect)
    assert m.overall.aupr == pytest.approx(1.0)
    assert m.overall.prec_at_90 == 1.0
    # With no predictions at all the official code returns an AUPR of 0.
    m = span_metrics(gold, {})
    assert m.overall.aupr == 0.0
    assert m.overall.prec_at_80 == 0.0


def test_duplicate_prediction_texts_keep_the_last_probability_like_the_official_code():
    gold = {("A", "Governing Law"): ["laws of New York"]}
    preds = {("A", "Governing Law"): [("laws of New York", 0.9), ("laws of New York", 0.2)]}
    curve = pr_curve(gold, preds)
    # At conf 0.5 the duplicate's later 0.2 has overwritten the 0.9, so nothing is predicted.
    assert curve.confs[49] == pytest.approx(0.5)
    assert curve.recalls[50] == 0


def test_per_category_metrics_and_categories_without_gold():
    gold = {
        ("A", "Parties"): ["Acme Inc."],
        ("A", "Price Restrictions"): [],
    }
    preds = {
        ("A", "Parties"): [("Acme Inc.", 0.8)],
        ("A", "Price Restrictions"): [("prices shall not increase", 0.4)],
    }
    m = span_metrics(gold, preds)
    assert m.per_category["Parties"].aupr == pytest.approx(1.0)
    # A category with no gold spans has undefined recall, so I report it as missing.
    assert m.per_category["Price Restrictions"].n_gold == 0
    assert math.isnan(m.per_category["Price Restrictions"].aupr)


def test_bootstrap_by_contract_gives_an_interval_around_the_point_estimate():
    gold, preds = _gold_and_preds()
    # I copy the two contracts a few times under new ids so resampling has room to vary.
    g2, p2 = {}, {}
    for k in range(10):
        for (cid, cat), v in gold.items():
            g2[(f"{cid}{k}", cat)] = v
            p2[(f"{cid}{k}", cat)] = preds[(cid, cat)]
    m = span_metrics(g2, p2, n_boot=200, seed=0)
    lo, hi = m.overall.ci["aupr"]
    assert lo <= m.overall.aupr <= hi
    assert hi - lo > 0
