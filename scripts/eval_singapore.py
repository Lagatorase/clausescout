"""Score ClauseScout on the hand-labelled Singapore contracts.

Each method runs exactly as the app runs it, from its app config (config/app-*.yaml), with the
threshold chosen on CUAD validation. Nothing is tuned on the Singapore labels: they are only a
test of how well the CUAD choices carry over to Singapore-law contracts.

For every fully labelled contract (all 11 types decided, clausescout/data/singapore.py) I run
the same steps as the app: extract, ground every quote word for word, keep the top 2 quotes per
type, apply the threshold, then the playbook. The report has:
- high-stakes found F2 per method, with 95% bootstrap intervals over contracts,
- results per clause type (present in how many contracts, hits, misses, found recall),
- precision and recall of the three playbook rules CUAD can't measure.

Each method's raw output is saved per contract in runs/singapore/<method>/partial.jsonl, so a
stopped run carries on where it left off and scoring again doesn't rerun the models.

Usage: python scripts/eval_singapore.py [--methods keywords qa hybrid] [--n-boot 1000]
"""

from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import yaml

from clausescout.data import singapore
from clausescout.data.cuad import HIGH_STAKES, Contract
from clausescout.data.singapore import LABEL_TYPES, PLAYBOOK_TYPES, RULE_TRUTH
from clausescout.findings import MAX_PER_TYPE, Finding, to_preds, top_per_type
from clausescout.grounding.verbatim import GroundingIndex, ground_findings
from clausescout.metrics.contract import contract_metrics
from clausescout.playbook.engine import apply_playbook, load_playbook

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = {
    "keywords": ROOT / "config" / "app-keywords.yaml",
    "qa": ROOT / "config" / "app-qa.yaml",
    "hybrid": ROOT / "config" / "app-hybrid.yaml",
}


def load_set(ids: list[str], text_dir: Path, label_dir: Path):
    """The fully labelled contracts with their text, plus why any others were left out."""
    contracts, labels, skipped = [], {}, {}
    for cid in ids:
        text_path = Path(text_dir) / f"{cid}.txt"
        lab = singapore.load_labels(cid, label_dir)
        if not text_path.exists():
            skipped[cid] = "not fetched"
        elif not singapore.is_complete(lab):
            skipped[cid] = f"{len(lab['labels'])} of {len(LABEL_TYPES)} types labelled"
        else:
            contracts.append(Contract(cid, text_path.read_text(encoding="utf-8")))
            labels[cid] = lab["labels"]
    return contracts, labels, skipped


def high_stakes_gold(labels: dict) -> dict:
    # The same gold shape as CUAD: (contract, type) -> quotes, an empty list when absent.
    return {(cid, t): [s["text"] for s in lab[t]["spans"]] if lab[t]["status"] == "present"
            else [] for cid, lab in labels.items() for t in HIGH_STAKES}


def run_method(name: str, method, contracts: list[Contract], runs_dir: Path) -> list[Finding]:
    """Grounded findings for every contract, reusing any saved raw output."""
    out = Path(runs_dir) / name
    out.mkdir(parents=True, exist_ok=True)
    partial = out / "partial.jsonl"
    done = {}
    if partial.exists():
        for line in partial.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            done[row["contract_id"]] = row
    kept_all = []
    for k, c in enumerate(contracts, 1):
        if c.id in done:
            raw = [Finding(**f) for f in done[c.id]["raw"]]
        else:
            # The method is only built when something still needs running (see main).
            if callable(method) and not hasattr(method, "extract"):
                method = method()
            t0 = time.perf_counter()
            raw = method.extract(c.id, c.text)
            with open(partial, "a", encoding="utf-8") as f:
                f.write(json.dumps({"contract_id": c.id, "seconds": time.perf_counter() - t0,
                                    "raw": [asdict(x) for x in raw]}) + "\n")
            print(f"  {name}: {k}/{len(contracts)} contracts", flush=True)
        kept, _ = ground_findings(raw, c.text, GroundingIndex(c.text),
                                  hints=[f.start for f in raw])
        kept_all.extend(kept)
    return kept_all


def _ratio(a: float, b: float) -> float:
    return a / b if b else math.nan


def score_method(contracts: list[Contract], labels: dict, findings: list[Finding],
                 threshold: float, rules: list, n_boot: int, seed: int = 0) -> dict:
    """Scores one method's grounded findings the way the CUAD numbers were scored."""
    shown = top_per_type(findings, MAX_PER_TYPE)
    gold = high_stakes_gold(labels)
    con = contract_metrics(gold, to_preds(shown), threshold=threshold, n_boot=n_boot, seed=seed)
    per_type = {}
    for t in HIGH_STAKES:
        p = con.per_category[t]
        per_type[t] = {"present": p.tp + p.fn, "predicted": p.tp + p.fp, "tp": p.tp, "fp": p.fp,
                       "fn": p.fn, "found": p.n_correct, "precision": p.precision,
                       "recall": p.recall, "found_recall": p.found_recall,
                       "found_f2": p.found_f2}

    # The playbook runs on what the app would show: top 2 per type, above the threshold.
    by_contract: dict[str, list[Finding]] = {c.id: [] for c in contracts}
    for f in shown:
        if f.score >= threshold and f.contract_id in by_contract:
            by_contract[f.contract_id].append(f)
    playbook = {}
    measured = [r for r in rules if r.id in RULE_TRUTH]
    for rule in measured:
        tp = fp = fn = tn = 0
        for c in contracts:
            fired = any(fl.rule.id == rule.id
                        for fl in apply_playbook([rule], by_contract[c.id], c.text))
            truth = RULE_TRUTH[rule.id]({t: labels[c.id][t]["status"] for t in LABEL_TYPES})
            tp += fired and truth
            fp += fired and not truth
            fn += truth and not fired
            tn += not truth and not fired
        playbook[rule.id] = {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
                             "precision": _ratio(tp, tp + fp), "recall": _ratio(tp, tp + fn)}

    n_shown = sum(f.score >= threshold for f in shown if f.category in HIGH_STAKES)
    return {
        "threshold": threshold,
        "high_stakes_found_f2": con.high_stakes["found_f2"],
        "high_stakes_found_f2_ci": con.high_stakes_ci.get("found_f2"),
        "high_stakes_found_recall": con.high_stakes["found_recall"],
        "high_stakes_quotes_per_contract": n_shown / max(len(contracts), 1),
        "per_type": per_type,
        "playbook": playbook,
    }


def _f(x: float | None) -> str:
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.3f}"


def write_report(result: dict, path: Path) -> None:
    lines = [
        "# Singapore evaluation",
        "",
        f"{result['n_contracts']} fully labelled Singapore-law contracts, scored on "
        f"{result['finished'][:10]}. Each method uses its app config and the threshold chosen on "
        "CUAD validation; nothing was tuned on these labels. Intervals are 95% bootstrap "
        f"intervals over contracts ({result['n_boot']} resamples). With this few contracts they "
        "are wide.",
        "",
    ]
    if result["skipped"]:
        lines += ["Left out: " + ", ".join(f"{k} ({v})" for k, v in result["skipped"].items())
                  + ".", ""]
    lines += ["## High-stakes found F2", "",
              "| Method | Threshold | High-stakes found F2 | Found recall | Quotes per contract |",
              "|---|---:|---:|---:|---:|"]
    for name, m in result["methods"].items():
        ci = m["high_stakes_found_f2_ci"]
        ci_text = f" ({ci[0]:.3f}-{ci[1]:.3f})" if ci else ""
        lines.append(f"| {name} | {m['threshold']} | {_f(m['high_stakes_found_f2'])}{ci_text} | "
                     f"{_f(m['high_stakes_found_recall'])} | "
                     f"{m['high_stakes_quotes_per_contract']:.1f} |")
    lines += ["", "## Per clause type", "",
              "Present: contracts with the clause. Found: flagged with a correct quote.", ""]
    for name, m in result["methods"].items():
        lines += [f"**{name}**", "", "| Type | Present | Predicted | Found | Found recall | "
                  "Found F2 |", "|---|---:|---:|---:|---:|---:|"]
        for t, p in m["per_type"].items():
            lines.append(f"| {t} | {p['present']} | {p['predicted']} | {p['found']} | "
                         f"{_f(p['found_recall'])} | {_f(p['found_f2'])} |")
        lines.append("")
    lines += ["## Playbook rules CUAD can't measure", "",
              "A rule's flag is right when the labels agree: no-arbitration when Arbitration is "
              "absent, arbitration-not-siac when Arbitration is present and SIAC Arbitration "
              "absent, no-data-protection when Data Protection is absent. These rules read the "
              "whole text, so they normally score the same for every method.", "",
              "| Method | Rule | Flagged | Right | Wrong | Missed | Precision | Recall |",
              "|---|---|---:|---:|---:|---:|---:|---:|"]
    for name, m in result["methods"].items():
        for rid, r in m["playbook"].items():
            lines.append(f"| {name} | {rid} | {r['tp'] + r['fp']} | {r['tp']} | {r['fp']} | "
                         f"{r['fn']} | {_f(r['precision'])} | {_f(r['recall'])} |")
    lines += ["", "Label counts for the playbook types: "
              + ", ".join(f"{t} present in {n}" for t, n in result["playbook_present"].items())
              + "."]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def evaluate(methods: dict, ids: list[str], text_dir: Path, label_dir: Path, runs_dir: Path,
             n_boot: int = 1000, seed: int = 0) -> dict:
    """methods maps a name to (extractor or a function that builds it, threshold)."""
    contracts, labels, skipped = load_set(ids, text_dir, label_dir)
    if not contracts:
        raise SystemExit("No fully labelled contracts yet; run scripts/label_tool.py first.")
    rules = load_playbook()
    out = {}
    for name, (method, threshold) in methods.items():
        findings = run_method(name, method, contracts, runs_dir)
        out[name] = score_method(contracts, labels, findings, threshold, rules, n_boot, seed)
    return {
        "finished": datetime.now(UTC).isoformat(timespec="seconds"),
        "n_contracts": len(contracts),
        "contracts": [c.id for c in contracts],
        "skipped": skipped,
        "n_boot": n_boot,
        "playbook_present": {t: sum(lab[t]["status"] == "present" for lab in labels.values())
                             for t in PLAYBOOK_TYPES},
        "methods": out,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--methods", nargs="+", default=list(CONFIGS), choices=list(CONFIGS))
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--text-dir", type=Path, default=singapore.TEXT_DIR)
    ap.add_argument("--label-dir", type=Path, default=singapore.LABEL_DIR)
    ap.add_argument("--runs-dir", type=Path, default=ROOT / "runs" / "singapore")
    ap.add_argument("--json", type=Path,
                    default=ROOT / "experiments" / "results" / "singapore.json")
    ap.add_argument("--report", type=Path, default=ROOT / "reports" / "singapore_eval.md")
    args = ap.parse_args()

    from clausescout.extraction import build_method

    methods = {}
    for name in args.methods:
        cfg = yaml.safe_load(CONFIGS[name].read_text(encoding="utf-8"))
        # Built lazily, so scoring saved output needs no model or Ollama.
        methods[name] = (lambda c=cfg: build_method(c["method"], c.get("params")),
                         cfg["threshold"])
    result = evaluate(methods, singapore.contract_ids(), args.text_dir, args.label_dir,
                      args.runs_dir, args.n_boot)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(result, indent=1), encoding="utf-8")
    write_report(result, args.report)
    print(f"Wrote {args.json} and {args.report}")


if __name__ == "__main__":
    main()
