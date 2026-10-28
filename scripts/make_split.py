"""Split CUAD's training contracts into train and validation, by contract.

I hold out about 15% of the official training contracts using iterative stratification
(Sechidis et al., 2011), so each clause type ends up in validation in roughly the same
proportion as in the whole training set, including the rare ones. I also add each contract's
length quartile as an extra label, so validation isn't skewed towards long contracts.
The test contracts are never touched here.
"""

import argparse
import random
from collections import Counter

import numpy as np

from clausescout.data.cuad import SPLIT_DIR, load_all, official_split


def contract_labels(contracts) -> dict[str, set[str]]:
    # Each contract's labels are its clause types plus a length quartile tag.
    lengths = {i: len(c.text.split()) for i, c in contracts.items()}
    cuts = np.percentile(list(lengths.values()), [25, 50, 75])
    return {
        i: c.present() | {f"len_q{int(np.searchsorted(cuts, lengths[i]))}"}
        for i, c in contracts.items()
    }


def stratified_split(contracts, frac: float, seed: int) -> tuple[list[str], list[str]]:
    rng = random.Random(seed)
    labels = contract_labels(contracts)
    unassigned = set(contracts)

    # How many contracts each split still wants, overall and per label.
    sizes = {"val": round(frac * len(contracts))}
    sizes["train"] = len(contracts) - sizes["val"]
    label_totals = Counter(lab for labs in labels.values() for lab in labs)
    want = {
        s: {lab: n * sizes[s] / len(contracts) for lab, n in label_totals.items()} for s in sizes
    }
    assigned: dict[str, str] = {}

    while unassigned:
        # I pick the label with the fewest unassigned contracts left, since it is the hardest
        # to balance, and deal out every contract that carries it.
        remaining = Counter(lab for i in unassigned for lab in labels[i])
        if not remaining:
            break
        lab = min(remaining, key=lambda k: (remaining[k], k))
        batch = sorted(i for i in unassigned if lab in labels[i])
        rng.shuffle(batch)
        for i in batch:
            # Each contract goes to the split that most wants this label, then the split with
            # the most room left, then a coin flip.
            split = max(sizes, key=lambda s: (want[s][lab], sizes[s], rng.random()))
            assigned[i] = split
            sizes[split] -= 1
            for other in labels[i]:
                want[split][other] -= 1
            unassigned.discard(i)

    train = sorted(i for i, s in assigned.items() if s == "train")
    val = sorted(i for i, s in assigned.items() if s == "val")
    return train, val


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--frac", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=13)
    args = parser.parse_args()

    contracts = load_all()
    train_ids, test_ids = official_split()
    train, val = stratified_split({i: contracts[i] for i in train_ids}, args.frac, args.seed)

    # I check the three lists are disjoint before writing anything.
    assert not set(train) & set(val) and not (set(train) | set(val)) & set(test_ids)

    SPLIT_DIR.mkdir(parents=True, exist_ok=True)
    for name, ids in [("train", train), ("val", val), ("test", sorted(test_ids))]:
        (SPLIT_DIR / f"{name}.txt").write_text("\n".join(ids) + "\n", encoding="utf-8")
    print(f"train={len(train)} val={len(val)} test={len(test_ids)} (seed {args.seed})")


if __name__ == "__main__":
    main()
