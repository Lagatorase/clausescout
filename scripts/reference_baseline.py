"""Score the trivial "every clause type is present" answer on validation, as a reference row.

It quotes nothing, so its span scores and "found" scores are zero. It shows how much of a
contract-level score comes from just saying yes to everything.

Usage: python scripts/reference_baseline.py
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from clausescout.data.cuad import CATEGORIES, load_split
from clausescout.experiments import git_commit, score_findings
from clausescout.findings import Finding

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    contracts = load_split("val")
    # One empty-ish finding per (contract, clause type). I use a single character that never
    # matches a gold span, so presence is always "yes" and no span is ever correct.
    findings = [Finding(c.id, cat, chr(0x2400), 1.0, method="always-present")
                for c in contracts for cat in CATEGORIES]
    result = {"name": "always-present", "config": {"method": "always-present"}, "split": "val",
              "finished": datetime.now(UTC).isoformat(timespec="seconds"),
              "contracts": len(contracts),
              **score_findings(contracts, findings, threshold=0.5, n_boot=1000),
              "grounding": None, "time": {"per_contract_s": 0.0}, "usage": {},
              "cost_per_contract_usd": 0.0, "git_commit": git_commit()}
    out = ROOT / "experiments" / "results" / "always-present.json"
    out.write_text(json.dumps(result, indent=1, default=float), encoding="utf-8")
    h = result["contract"]["high_stakes"]
    print(f"High-stakes F2 {h['f2']:.3f}, recall {h['recall']:.3f}; saved {out.name}")


if __name__ == "__main__":
    main()
