"""Write examples of what a method gets wrong, per high-stakes clause type.

For each type I count three kinds of error in what a reviewer would see (the top 2 quotes per
clause type, then the run's threshold) and show a few examples:
- missed: the contract has the clause, and nothing above the threshold was predicted;
- false alarm: something was predicted, but the contract has no such clause;
- wrong quote: the clause was found, but no predicted quote matches a gold span.

Usage: python scripts/error_analysis.py qa-small-e1-s0 [--examples 3]
"""

import argparse
import json
import random
from pathlib import Path

from clausescout.data.cuad import HIGH_STAKES, load_split
from clausescout.findings import Finding, top_per_type
from clausescout.metrics.span import is_match

ROOT = Path(__file__).resolve().parents[1]


def short(text: str, n: int = 300) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[:n] + "..."


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--examples", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    result = json.loads((ROOT / "experiments" / "results" / f"{args.name}.json").read_text("utf-8"))
    threshold, split = result["threshold"], result["split"]
    contracts = {c.id: c for c in load_split(split)}
    with open(ROOT / "runs" / args.name / "findings.jsonl", encoding="utf-8") as f:
        findings = [Finding(**json.loads(line)) for line in f]
    # The same cap the metrics use, so these examples explain the scores in the tables.
    preds: dict[tuple[str, str], list[dict]] = {}
    for p in top_per_type(findings, result.get("max_per_type")):
        if p.score >= threshold:
            preds.setdefault((p.contract_id, p.category), []).append(
                {"text": p.text, "score": p.score})

    rng = random.Random(args.seed)
    lines = [f"# Error analysis: {args.name} ({split}, threshold {threshold})", "",
             "Examples are picked at random (seed fixed) so they are not the most flattering or "
             "the worst. Quotes are shortened to 300 characters.", ""]
    for cat in HIGH_STAKES:
        missed, alarms, wrong = [], [], []
        for cid, c in contracts.items():
            gold = [s.text for s in c.labels.get(cat, [])]
            got = preds.get((cid, cat), [])
            if gold and not got:
                missed.append((cid, gold[0]))
            elif got and not gold:
                alarms.append((cid, max(got, key=lambda p: p["score"])))
            elif gold and got and not any(is_match(g, p["text"], cat) for g in gold for p in got):
                wrong.append((cid, gold[0], max(got, key=lambda p: p["score"])))
        lines += [f"## {cat}", "",
                  f"{len(missed)} missed, {len(alarms)} false alarms, {len(wrong)} found with "
                  "the wrong quote.", ""]
        for cid, g in rng.sample(missed, min(args.examples, len(missed))):
            lines.append(f"- Missed in *{cid[:60]}*: \"{short(g)}\"")
        for cid, p in rng.sample(alarms, min(args.examples, len(alarms))):
            lines.append(f"- False alarm in *{cid[:60]}* (score {p['score']:.2f}): "
                         f"\"{short(p['text'])}\"")
        for cid, g, p in rng.sample(wrong, min(args.examples, len(wrong))):
            lines.append(f"- Wrong quote in *{cid[:60]}*: gave \"{short(p['text'], 200)}\", "
                         f"gold starts \"{short(g, 200)}\"")
        lines.append("")
    out = ROOT / "reports" / f"error_analysis_{args.name}.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
