"""Check my span metrics against the official CUAD evaluate.py on random predictions.

Get evaluate.py from https://github.com/TheAtticusProject/cuad and pass its path. I run its
metric functions (not its command-line part) on noisy predictions over the validation
contracts and compare AUPR and precision at 80% and 90% recall, overall and per clause type.

Usage: python scripts/crosscheck_official.py path/to/evaluate.py
"""

import argparse
import random

from clausescout.data.cuad import load_split
from clausescout.metrics.span import gold_from_contracts, span_metrics

CHECK_TYPES = ["Parties", "Governing Law", "Cap On Liability", "Source Code Escrow",
               "Change Of Control", "Exclusivity"]


def load_official(path: str) -> dict:
    # The official file reads a CSV at import time and has a __main__ block; I only need its
    # functions, so I drop both before running it.
    src = open(path, encoding="utf-8").read().replace("qtype_dict = get_questions_from_csv()", "")
    src = src.split('if __name__ == "__main__":')[0]
    namespace: dict = {}
    exec(src, namespace)
    return namespace


def noisy_predictions(contracts, rng):
    """Mostly-right answers (gold prefixes) mixed with random text and the odd duplicate."""
    preds = {}
    for c in contracts:
        words = c.text.split(" ")
        for cat, spans in c.labels.items():
            out = []
            for s in spans:
                if rng.random() < 0.97:
                    w = s.text.split(" ")
                    out.append((" ".join(w[: rng.randint(max(1, len(w) // 3), len(w))]),
                                rng.random()))
            for _ in range(rng.randint(0, 3)):
                i = rng.randrange(len(words))
                out.append((" ".join(words[i : i + rng.randint(1, 40)]), rng.random() ** 3))
            # Duplicate texts test the official "last probability wins" behaviour.
            if rng.random() < 0.05 and out:
                out.append((out[0][0], rng.random()))
            preds[(c.id, cat)] = out
    return preds


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("evaluate_py")
    ap.add_argument("--trials", type=int, default=3)
    args = ap.parse_args()
    off = load_official(args.evaluate_py)
    contracts = load_split("val")
    gold = gold_from_contracts(contracts)
    og = {f"{a}__{b}": v for (a, b), v in gold.items()}
    rng = random.Random(0)

    for trial in range(args.trials):
        preds = noisy_predictions(contracts, rng)
        mine = span_metrics(gold, preds)
        op = {f"{a}__{b}": [{"text": t, "probability": p} for t, p in v]
              for (a, b), v in preds.items()}

        def official(cat=None, op=op):
            p, r, c = off["get_precisions_recalls"](op, og, category=cat)
            return (off["get_aupr"](p, r), off["get_prec_at_recall"](p, r, c, 0.8)[0],
                    off["get_prec_at_recall"](p, r, c, 0.9)[0])

        o = official()
        m = (mine.overall.aupr, mine.overall.prec_at_80, mine.overall.prec_at_90)
        worst = max(abs(a - b) for a, b in zip(o, m, strict=True))
        for cat in CHECK_TYPES:
            s = mine.per_category[cat]
            worst = max(worst, *(abs(a - b) for a, b in
                                 zip(official(cat), (s.aupr, s.prec_at_80, s.prec_at_90),
                                     strict=True)))
        print(f"trial {trial}: official AUPR {o[0]:.6f}, mine {m[0]:.6f}; "
              f"largest difference anywhere {worst:.2e}")


if __name__ == "__main__":
    main()
