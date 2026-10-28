"""Run one experiment from experiments/experiments.yaml and save its results.

Results go to experiments/results/<name>.json (committed, so the report can be rebuilt) and the
grounded findings to runs/<name>/findings.jsonl (gitignored, for error analysis and the hybrid).

Usage: python scripts/run_experiment.py keywords-v1 [--limit 5]
"""

import argparse
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import yaml

from clausescout.data.cuad import load_split
from clausescout.experiments import run_experiment
from clausescout.extraction import build_method

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "experiments" / "experiments.yaml"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--limit", type=int, help="only the first N contracts, for a quick check")
    args = ap.parse_args()

    configs = {e["name"]: e for e in yaml.safe_load(CONFIG.read_text())["experiments"]}
    cfg = configs[args.name]
    split = cfg.get("split", "val")
    # The test split is used once, at the end, so I make running it a deliberate choice.
    if split == "test" and not cfg.get("final", False):
        sys.exit("Test-split runs need final: true in the config.")
    contracts = load_split(split)[: args.limit]
    (ROOT / "runs" / args.name).mkdir(parents=True, exist_ok=True)

    method = build_method(cfg["method"], cfg.get("params"))
    summary, findings = run_experiment(
        method, contracts, threshold=cfg.get("threshold", 0.5), n_boot=cfg.get("n_boot", 0),
        progress=True,
        # Full runs save each contract as they go, so an interrupted run picks up where it was.
        resume_path=None if args.limit else ROOT / "runs" / args.name / "partial.jsonl",
    )
    summary = {"name": args.name, "config": cfg, "split": split,
               "finished": datetime.now(UTC).isoformat(timespec="seconds"), **summary}
    if args.limit:
        print("Limited run, so I'm not saving results.")
    else:
        out = ROOT / "experiments" / "results" / f"{args.name}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=1, default=float), encoding="utf-8")
        runs = ROOT / "runs" / args.name
        runs.mkdir(parents=True, exist_ok=True)
        with open(runs / "findings.jsonl", "w", encoding="utf-8") as f:
            for finding in findings:
                f.write(json.dumps(asdict(finding)) + "\n")
        print(f"Saved {out.relative_to(ROOT)}")

    s, c, g = summary["span"]["overall"], summary["contract"], summary["grounding"]
    print(f"Span AUPR {s['aupr']:.3f}, P@80R {s['prec_at_80']:.3f}, P@90R {s['prec_at_90']:.3f}")
    print(f"Contract micro F1 {c['micro']['f1']:.3f}, high-stakes recall "
          f"{c['high_stakes']['recall']:.3f}, high-stakes F2 {c['high_stakes']['f2']:.3f}")
    print(f"Grounding rejected {g['rejected']}/{g['submitted']} ({g['rejection_rate']:.1%}); "
          f"{summary['time']['per_contract_s']:.2f}s per contract")


if __name__ == "__main__":
    main()
