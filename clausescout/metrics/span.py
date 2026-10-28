"""Span-level metrics that follow CUAD's official evaluation protocol.

I reimplemented evaluate.py from github.com/TheAtticusProject/cuad so my numbers can sit next
to the paper's Table 2 (Hendrycks et al., 2021). The rules I kept, quirks included:
- A prediction matches a gold span when the Jaccard similarity of their word sets is at least
  0.5. Words come from lowercasing, deleting . , ; : and turning / into a space, then splitting
  on single spaces. (The paper says "remove punctuation", but the code only removes these four.)
- For Parties, a prediction also matches if it contains the gold span as a substring.
- Each gold span with a matching prediction is a true positive, each gold span without one is a
  false negative, and each prediction that matches no gold span is a false positive.
- Predictions are kept when their probability is strictly above a threshold, swept over
  0.99, 0.98, ..., 0.01, 0.001 and 0. Empty predictions are ignored and duplicate texts keep
  the last probability seen.
- Precision is smoothed so it never rises as recall falls, AUPR is the trapezoid area under that
  curve up to the highest recall reached, and precision at X% recall is the smoothed precision
  at the first threshold that reaches X%. The official code zips the curve with the threshold
  list, which is one shorter, so the conf 0 point never counts for precision at recall.

Overall scores pool every (contract, category) pair, like the paper. On top of that I add
per-category scores and bootstrap confidence intervals by resampling contracts.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

import numpy as np

IOU_THRESH = 0.5
CONF_THRESHOLDS: list[float] = [float(c) for c in np.arange(0.99, 0, -0.01)] + [0.001, 0]

# Gold maps (contract id, category) to gold span texts; predictions map the same keys to
# (text, probability) pairs.
Key = tuple[str, str]
Gold = Mapping[Key, Sequence[str]]
Preds = Mapping[Key, Sequence[tuple[str, float]]]


def jaccard(gt: str, pred: str) -> float:
    """Word-set Jaccard similarity exactly as CUAD's evaluate.py computes it."""
    for token in (".", ",", ";", ":"):
        gt = gt.replace(token, "")
        pred = pred.replace(token, "")
    gt_words = set(gt.lower().replace("/", " ").split(" "))
    pred_words = set(pred.lower().replace("/", " ").split(" "))
    return len(gt_words & pred_words) / len(gt_words | pred_words)


def is_match(gt: str, pred: str, category: str) -> bool:
    if category == "Parties" and gt in pred:
        return True
    return jaccard(gt, pred) >= IOU_THRESH


def gold_from_contracts(contracts: Iterable, categories: Iterable[str] | None = None) -> dict:
    """Builds the gold dict from loaded CUAD contracts, one key per contract and category."""
    gold = {}
    for c in contracts:
        for cat in categories or c.labels:
            gold[(c.id, cat)] = [s.text for s in c.labels.get(cat, [])]
    return gold


@dataclass
class Curve:
    # Raw (unsmoothed) points, starting with the official (recall 0, precision 1) anchor.
    precisions: list[float]
    recalls: list[float]
    confs: list[float]


@dataclass
class SpanScores:
    aupr: float
    prec_at_80: float
    prec_at_90: float
    n_gold: int
    n_contracts: int
    # Metric name to a (low, high) 95% bootstrap interval, filled when bootstrapping.
    ci: dict[str, tuple[float, float]] = field(default_factory=dict)


@dataclass
class SpanMetrics:
    overall: SpanScores
    per_category: dict[str, SpanScores]

    @property
    def macro_aupr(self) -> float:
        # Mean AUPR over categories that have gold spans, so rare types count as much as common.
        vals = [s.aupr for s in self.per_category.values() if s.n_gold > 0]
        return float(np.mean(vals)) if vals else math.nan


class _Items:
    """Per-span probabilities that decide TP and FP at any threshold.

    A gold span is a TP at threshold t when its best matching prediction has probability > t.
    An unmatched prediction is a FP when its own probability is > t. Matched predictions never
    count as FP, so I can drop them. That turns every threshold into a simple count.
    """

    def __init__(self, gold: Gold, preds: Preds):
        unknown = set(preds) - set(gold)
        if unknown:
            raise ValueError(f"Predictions for keys with no gold entry: {sorted(unknown)[:3]}")
        self.contracts = sorted({cid for cid, _ in gold})
        self.categories = sorted({cat for _, cat in gold})
        cidx = {c: i for i, c in enumerate(self.contracts)}
        catidx = {c: i for i, c in enumerate(self.categories)}
        tp_prob, tp_c, tp_cat, fp_prob, fp_c, fp_cat = [], [], [], [], [], []
        for (cid, cat), answers in gold.items():
            # Same dedupe as the official code: later duplicates overwrite earlier ones.
            texts: dict[str, float] = {}
            for text, prob in preds.get((cid, cat), []):
                if text != "":
                    texts[text] = float(prob)
            matched = set()
            for ans in answers:
                best = -math.inf
                for text, prob in texts.items():
                    if is_match(ans, text, cat):
                        matched.add(text)
                        best = max(best, prob)
                tp_prob.append(best)
                tp_c.append(cidx[cid])
                tp_cat.append(catidx[cat])
            for text, prob in texts.items():
                if text not in matched:
                    fp_prob.append(prob)
                    fp_c.append(cidx[cid])
                    fp_cat.append(catidx[cat])
        self.tp_prob, self.fp_prob = np.asarray(tp_prob, float), np.asarray(fp_prob, float)
        self.tp_c, self.fp_c = np.asarray(tp_c, int), np.asarray(fp_c, int)
        self.tp_cat, self.fp_cat = np.asarray(tp_cat, int), np.asarray(fp_cat, int)
        self.gold_contracts = {
            cat: {cid for (cid, c), a in gold.items() if c == cat} for cat in self.categories
        }

    def counts(self, weights: np.ndarray, cat: int | None) -> tuple[np.ndarray, np.ndarray, float]:
        """TP and FP at every threshold, plus the number of gold spans, for contract weights."""
        conf = np.asarray(CONF_THRESHOLDS)

        def above(prob, c, k):
            mask = np.ones(len(prob), bool) if cat is None else (k == cat)
            p, w = prob[mask], weights[c[mask]]
            # I sort by probability once, then a binary search counts the weighted items
            # strictly above each threshold. Unmatched gold spans sit at -inf and never count.
            order = np.argsort(-p, kind="stable")
            cw = np.concatenate([[0.0], np.cumsum(w[order])])
            return cw[np.searchsorted(-p[order], -conf, side="left")], float(w.sum())

        tp, n_gold = above(self.tp_prob, self.tp_c, self.tp_cat)
        fp, _ = above(self.fp_prob, self.fp_c, self.fp_cat)
        return tp, fp, n_gold


def _curve_from_counts(tp: np.ndarray, fp: np.ndarray, n_gold: float) -> Curve:
    precisions, recalls = [1.0], [0.0]
    for t, f in zip(tp, fp, strict=True):
        precisions.append(t / (t + f) if t + f > 0 else math.nan)
        recalls.append(t / n_gold if n_gold > 0 else math.nan)
    return Curve(precisions, recalls, list(CONF_THRESHOLDS))


def _smooth(precisions: list[float]) -> list[float]:
    # Running max from the high-recall end. I use Python's max on purpose, because it treats
    # NaN the same order-dependent way the official code does.
    best = precisions[::-1]
    for i in range(1, len(best)):
        best[i] = max(best[i - 1], best[i])
    return best[::-1]


def _scores(curve: Curve) -> tuple[float, float, float]:
    smoothed = _smooth(curve.precisions)
    aupr = float(np.trapezoid(smoothed, curve.recalls))
    if math.isnan(aupr):
        aupr = 0.0

    def prec_at(thresh: float) -> float:
        # zip with confs drops the last (conf 0) point, matching the official code.
        for prec, rec, _ in zip(smoothed, curve.recalls, curve.confs):  # noqa: B905
            if rec >= thresh:
                return float(prec)
        return 0.0

    return aupr, prec_at(0.8), prec_at(0.9)


def pr_curve(gold: Gold, preds: Preds, category: str | None = None) -> Curve:
    items = _Items(gold, preds)
    cat = None if category is None else items.categories.index(category)
    return _curve_from_counts(*items.counts(np.ones(len(items.contracts)), cat))


def span_metrics(gold: Gold, preds: Preds, n_boot: int = 0, seed: int = 0) -> SpanMetrics:
    """Overall and per-category AUPR and precision at 80% and 90% recall.

    With n_boot > 0 I also resample contracts with replacement and attach 95% percentile
    intervals. Categories without any gold spans get NaN, since recall is undefined there.
    """
    items = _Items(gold, preds)
    n = len(items.contracts)
    ones = np.ones(n)

    def score(weights, cat):
        tp, fp, n_gold = items.counts(weights, cat)
        if cat is not None and n_gold == 0:
            return (math.nan, math.nan, math.nan), 0
        return _scores(_curve_from_counts(tp, fp, n_gold)), n_gold

    targets: list[tuple[str | None, int | None]] = [(None, None)]
    targets += [(c, i) for i, c in enumerate(items.categories)]
    results = {}
    for name, cat in targets:
        (aupr, p80, p90), n_gold = score(ones, cat)
        n_contracts = n if name is None else len(items.gold_contracts[name])
        results[name] = SpanScores(aupr, p80, p90, int(n_gold), n_contracts)

    if n_boot > 0:
        rng = np.random.default_rng(seed)
        samples = {name: [] for name, _ in targets}
        for _ in range(n_boot):
            # One resample of contracts, shared by every category so the intervals line up.
            weights = np.bincount(rng.integers(0, n, n), minlength=n).astype(float)
            for name, cat in targets:
                samples[name].append(score(weights, cat)[0])
        for name, rows in samples.items():
            arr = np.asarray(rows, float)
            for j, metric in enumerate(("aupr", "prec_at_80", "prec_at_90")):
                col = arr[:, j][~np.isnan(arr[:, j])]
                if len(col):
                    lo, hi = np.percentile(col, [2.5, 97.5])
                    results[name].ci[metric] = (float(lo), float(hi))

    overall = results.pop(None)
    return SpanMetrics(overall, results)
