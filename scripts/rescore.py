"""Re-score a finished validation run from its saved findings, without running the method again.

I use it to pick each method's contract-level threshold on validation, the same way for every
method: sweep thresholds, keep the one with the highest mean high-stakes F2, then rewrite the
results file at that threshold with 95% bootstrap intervals.

Usage: python scripts/rescore.py qa-small-e1-s0 [--n-boot 1000] [--threshold 0.3]
"""

import argparse
import json
from pathlib import Path

import numpy as np

from clausescout.data.cuad import CATEGORIES, load_split
from clausescout.experiments import score_findings
from clausescout.findings import Finding, to_preds
from clausescout.metrics.contract import contract_metrics
from clausescout.metrics.span import gold_from_contracts

ROOT = Path(__file__).resolve().parents[1]
GRID = [round(t, 2) for t in np.arange(0.05, 1.0, 0.05)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--threshold", type=float, help="skip the sweep and use this threshold")
    args = ap.parse_args()

    out = ROOT / "experiments" / "results" / f"{args.name}.json"
    result = json.loads(out.read_text(encoding="utf-8"))
    # The sweep picks a setting, so it must only ever see validation.
    if result["split"] != "val":
        raise SystemExit("Thresholds are chosen on validation only.")
    contracts = load_split("val")
    with open(ROOT / "runs" / args.name / "findings.jsonl", encoding="utf-8") as f:
        findings = [Finding(**json.loads(line)) for line in f]

    sweep = []
    if args.threshold is None:
        gold, preds = gold_from_contracts(contracts, CATEGORIES), to_preds(findings)
        print("threshold  hs-F2  hs-recall  hs-precision  micro-F1  hs-found-F2")
        for t in GRID:
            m = contract_metrics(gold, preds, threshold=t)
            h = m.high_stakes
            sweep.append({"threshold": t, "high_stakes_f2": h["f2"], "high_stakes_recall":
                          h["recall"], "high_stakes_precision": h["precision"],
                          "micro_f1": m.micro.f1, "high_stakes_found_f2": h["found_f2"]})
            print(f"{t:9.2f}  {h['f2']:.3f}  {h['recall']:9.3f}  {h['precision']:12.3f}  "
                  f"{m.micro.f1:.3f}  {h['found_f2']:.3f}")
        # Ties go to the higher threshold, which gives the reader fewer findings to check.
        best = max(sweep, key=lambda r: (round(r["high_stakes_f2"], 6), r["threshold"]))
        threshold = best["threshold"]
        print(f"Chosen threshold {threshold} (high-stakes F2 {best['high_stakes_f2']:.3f})")
    else:
        threshold = args.threshold

    result.update(score_findings(contracts, findings, threshold, n_boot=args.n_boot))
    result["threshold_sweep"] = sweep
    result["threshold_chosen_by"] = (
        "max mean high-stakes F2 on validation" if sweep else "set by hand")
    out.write_text(json.dumps(result, indent=1, default=float), encoding="utf-8")
    h, ci = result["contract"]["high_stakes"], result["contract"]["high_stakes_ci"]
    lo, hi = ci.get("f2", (float("nan"), float("nan")))
    print(f"High-stakes F2 {h['f2']:.3f} ({lo:.3f}-{hi:.3f}); saved {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
