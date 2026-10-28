"""Contract-level metrics: does the contract have this clause, and did we quote it correctly.

This is the question a due diligence report answers, so I score each (contract, clause type)
pair once instead of each span:
- Presence: a clause type is predicted present when any prediction clears the threshold.
  Precision, recall, F1 and F2 (which counts recall twice as much as precision, because a
  missed clause hurts more than an extra one to read) follow from that.
- Span correctness: for true positives, did at least one kept prediction match a gold span
  under CUAD's Jaccard rule. found_recall combines both: the share of contracts with the
  clause where we flagged it and quoted it correctly. found_f2 is F2 where a "yes" only counts
  as a hit when it comes with a correct quote, so saying yes to everything can't score well.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field

import numpy as np

from clausescout.data.cuad import HIGH_STAKES
from clausescout.metrics.span import Gold, Preds, is_match

METRICS = ("precision", "recall", "f1", "f2", "span_correct", "found_recall", "found_f2")


@dataclass
class PresenceScores:
    tp: int
    fp: int
    fn: int
    tn: int
    n_correct: int
    precision: float
    recall: float
    f1: float
    f2: float
    span_correct: float
    found_recall: float
    found_f2: float
    ci: dict[str, tuple[float, float]] = field(default_factory=dict)


@dataclass
class ContractMetrics:
    per_category: dict[str, PresenceScores]
    micro: PresenceScores
    # Unweighted means over categories that have at least one contract with the clause.
    macro: dict[str, float]
    high_stakes: dict[str, float]
    # 95% bootstrap intervals for the macro and high-stakes means, when n_boot > 0.
    macro_ci: dict[str, tuple[float, float]] = field(default_factory=dict)
    high_stakes_ci: dict[str, tuple[float, float]] = field(default_factory=dict)


def _ratio(a: float, b: float) -> float:
    return a / b if b > 0 else math.nan


def _from_counts(tp, fp, fn, tn, correct) -> tuple[float, ...]:
    # I use the count forms of F1 and F2 so they are 0 (not NaN) when there are misses
    # or false alarms but no hits.
    return (
        _ratio(tp, tp + fp),
        _ratio(tp, tp + fn),
        _ratio(2 * tp, 2 * tp + fp + fn),
        _ratio(5 * tp, 5 * tp + 4 * fn + fp),
        _ratio(correct, tp),
        _ratio(correct, tp + fn),
        # Gold clauses without a correct quote count as misses, other "yes" answers as false alarms.
        _ratio(5 * correct, 5 * correct + 4 * (tp + fn - correct) + (tp + fp - correct)),
    )


def contract_metrics(
    gold: Gold,
    preds: Preds,
    threshold: float | Mapping[str, float] = 0.5,
    n_boot: int = 0,
    seed: int = 0,
) -> ContractMetrics:
    """Presence and span-correctness metrics per clause type, with optional bootstrap CIs.

    threshold can be one number or a per-category mapping. A prediction counts when its
    probability is at least the threshold. Methods without scores should use probability 1.
    """
    contracts = sorted({cid for cid, _ in gold})
    categories = sorted({cat for _, cat in gold})
    cidx = {c: i for i, c in enumerate(contracts)}
    rows = []  # contract index, category index, gold present, predicted present, correct span
    for (cid, cat), answers in gold.items():
        t = threshold[cat] if isinstance(threshold, Mapping) else threshold
        kept = [text for text, prob in preds.get((cid, cat), []) if text and prob >= t]
        correct = any(is_match(a, p, cat) for a in answers for p in kept)
        rows.append((cidx[cid], categories.index(cat), bool(answers), bool(kept), correct))
    arr = np.asarray(rows, dtype=int).reshape(-1, 5)
    c, k = arr[:, 0], arr[:, 1]
    g, p, ok = (arr[:, j].astype(bool) for j in (2, 3, 4))

    def counts(weights, mask):
        # Weighted confusion counts for the rows in mask, so bootstrap resamples are cheap.
        w = weights[c] * mask
        return tuple(
            float(w[sel].sum()) for sel in (g & p, ~g & p, g & ~p, ~g & ~p, g & p & ok)
        )

    masks = {cat: k == i for i, cat in enumerate(categories)}
    masks[None] = np.ones(len(k), bool)

    def summarise(per_cat_values: dict[str, tuple], names: list[str]) -> dict[str, float]:
        vals = [per_cat_values[n] for n in names if n in per_cat_values]
        out = {}
        for j, metric in enumerate(METRICS):
            col = [v[j] for v in vals if not math.isnan(v[j])]
            out[metric] = float(np.mean(col)) if col else math.nan
        return out

    def evaluate(weights):
        # Every score for one set of contract weights: per category, micro, macro, high-stakes.
        per = {}
        for name, mask in masks.items():
            cnt = counts(weights, mask)
            per[name] = (cnt, _from_counts(*cnt))
        with_gold = [n for n in categories if per[n][0][0] + per[n][0][2] > 0]
        scores = {n: per[n][1] for n in categories}
        macro = summarise(scores, with_gold)
        high = summarise(scores, [n for n in HIGH_STAKES if n in with_gold])
        return per, macro, high

    per, macro, high = evaluate(np.ones(len(contracts)))
    results = {
        name: PresenceScores(*(int(x) for x in cnt), *vals) for name, (cnt, vals) in per.items()
    }

    if n_boot > 0:
        rng = np.random.default_rng(seed)
        samples = {name: [] for name in results}
        means = {"macro": [], "high": []}
        n = len(contracts)
        for _ in range(n_boot):
            weights = np.bincount(rng.integers(0, n, n), minlength=n).astype(float)
            b_per, b_macro, b_high = evaluate(weights)
            means["macro"].append(b_macro)
            means["high"].append(b_high)
            for name, (_, vals) in b_per.items():
                samples[name].append(vals)
        for name, vals in samples.items():
            arr_v = np.asarray(vals, float)
            for j, metric in enumerate(METRICS):
                col = arr_v[:, j][~np.isnan(arr_v[:, j])]
                if len(col):
                    lo, hi = np.percentile(col, [2.5, 97.5])
                    results[name].ci[metric] = (float(lo), float(hi))

    def mean_ci(dicts):
        out = {}
        for metric in METRICS:
            col = [d[metric] for d in dicts if not math.isnan(d[metric])]
            if col:
                lo, hi = np.percentile(col, [2.5, 97.5])
                out[metric] = (float(lo), float(hi))
        return out

    micro = results.pop(None)
    if n_boot > 0:
        return ContractMetrics(results, micro, macro, high, mean_ci(means["macro"]),
                               mean_ci(means["high"]))
    return ContractMetrics(results, micro, macro, high)
