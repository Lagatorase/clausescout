"""Compare two local LLM runs on the validation contracts both of them finished.

I use it to check llm-qwen7b-v2 (answer cap) against llm-qwen7b-v1 (no cap) on the 23 contracts
v1 finished before it failed. Both runs use temperature 0 and a fixed seed, and v2's cap only
cuts answers that fill the window (one v1 request did), so v2 should reproduce v1 elsewhere. The report says how many findings match and
compares high-stakes found F2 on those contracts at the same threshold.

Usage: python scripts/compare_llm_runs.py llm-qwen7b-v1 llm-qwen7b-v2
"""

import argparse
import json
from pathlib import Path

from clausescout.data.cuad import load_split
from clausescout.experiments import score_findings
from clausescout.findings import Finding
from clausescout.grounding.verbatim import GroundingIndex, ground_findings, normalise

ROOT = Path(__file__).resolve().parents[1]
# Set before v2 ran: with deterministic decoding and a cap that only cuts window-filling answers,
# more difference than this means the runs aren't comparable and I check with you first.
MIN_MATCH = 0.95
MAX_F2_GAP = 0.02


def raw_by_contract(name: str) -> dict[str, list[Finding]]:
    # partial.jsonl holds every finished contract's raw findings, before grounding.
    rows = {}
    with open(ROOT / "runs" / name / "partial.jsonl", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            rows[row["contract_id"]] = [Finding(**x) for x in row["raw"]]
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--threshold", type=float, help="instead of the new run's own threshold")
    ap.add_argument("--no-save", action="store_true", help="print only, for a quick check")
    args = ap.parse_args()

    old, new = raw_by_contract(args.old), raw_by_contract(args.new)
    contracts = [c for c in load_split("val") if c.id in old and c.id in new]
    # Both runs are scored at the new run's threshold (chosen on all 62 contracts), so the only
    # difference is the findings themselves.
    threshold = args.threshold
    if threshold is None:
        result = json.loads((ROOT / "experiments" / "results" / f"{args.new}.json")
                            .read_text(encoding="utf-8"))
        threshold = result["threshold"]

    def key(f: Finding) -> tuple[str, str, str]:
        return f.contract_id, f.category, normalise(f.text)

    lines = [f"# {args.old} against {args.new} on the contracts both finished", ""]
    lines.append(f"{len(contracts)} validation contracts; threshold {threshold} (from "
                 f"{args.new} unless set by hand); top 2 quotes per type, as in rule 2.")
    lines.append("")
    scores = {}
    for name, raw in ((args.old, old), (args.new, new)):
        kept = []
        for c in contracts:
            # The same grounding step as the runner, so only quotes a reviewer would see count.
            found = raw[c.id]
            ok, _ = ground_findings(found, c.text, GroundingIndex(c.text),
                                    hints=[f.start for f in found])
            kept.extend(ok)
        s = score_findings(contracts, kept, threshold, n_boot=args.n_boot)
        h, ci = s["contract"]["high_stakes"], s["contract"]["high_stakes_ci"]
        scores[name] = (h["found_f2"], ci.get("found_f2"), len(kept))

    a = {key(f) for c in contracts for f in old[c.id]}
    b = {key(f) for c in contracts for f in new[c.id]}
    both = a & b
    match = len(both) / max(len(a | b), 1)
    gap = abs(scores[args.new][0] - scores[args.old][0])
    lines += [
        "| | Raw findings | Grounded findings | High-stakes found F2 |",
        "|---|---:|---:|---:|",
    ]
    for name, raw in ((args.old, a), (args.new, b)):
        f2, ci, n_kept = scores[name]
        ci_txt = f" ({ci[0]:.3f}-{ci[1]:.3f})" if ci else ""
        lines.append(f"| {name} | {len(raw)} | {n_kept} | {f2:.3f}{ci_txt} |")
    lines += [
        "",
        f"Findings in both runs (same contract, type and quote): {len(both)}; only in "
        f"{args.old}: {len(a - b)}; only in {args.new}: {len(b - a)}. Share matching: "
        f"{match:.1%}.",
        f"Difference in high-stakes found F2: {gap:.3f}.",
        "",
        f"Expected beforehand: at least {MIN_MATCH:.0%} matching and a found F2 gap of at most "
        f"{MAX_F2_GAP}. "
        + ("Within that, so v2 can stand in for v1." if match >= MIN_MATCH and gap <= MAX_F2_GAP
           else "Outside the limits I set beforehand; see the experiment report."),
    ]
    print("\n".join(lines))
    if args.no_save:
        return
    out = ROOT / "reports" / f"compare_{args.old}_{args.new}.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
