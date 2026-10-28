"""The one shape every extraction method returns, so metrics, grounding and reports share it."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

# Every method shows at most this many quotes per clause type per contract (selection rule 2).
MAX_PER_TYPE = 2


@dataclass
class Finding:
    contract_id: str
    category: str
    # After grounding this is the exact text from the contract, not what the method returned.
    text: str
    # Confidence in [0, 1]. Methods without scores (patterns, LLM answers) use 1.0.
    score: float = 1.0
    # Character offsets into the contract text, set by the grounding check.
    start: int | None = None
    end: int | None = None
    method: str = ""


def to_preds(findings: Iterable[Finding]) -> dict[tuple[str, str], list[tuple[str, float]]]:
    """Groups findings into the (contract, category) -> [(text, score)] form the metrics use."""
    preds: dict[tuple[str, str], list[tuple[str, float]]] = defaultdict(list)
    for f in findings:
        preds[(f.contract_id, f.category)].append((f.text, f.score))
    return dict(preds)


def top_per_type(findings: Iterable[Finding], k: int | None) -> list[Finding]:
    """Keeps each method's best k distinct quotes per (contract, clause type).

    A reviewer only reads the first few quotes per clause type, so every method is scored and
    shown with the same cap. Identical quotes count once, at their best score.
    """
    if k is None:
        return list(findings)
    groups: dict[tuple[str, str], dict[str, Finding]] = defaultdict(dict)
    for f in findings:
        seen = groups[(f.contract_id, f.category)]
        if f.text not in seen or f.score > seen[f.text].score:
            seen[f.text] = f
    out = []
    for seen in groups.values():
        # Ties on score go to the quote that comes first in the contract, so the cap is stable.
        ranked = sorted(seen.values(), key=lambda f: (-f.score, f.start or 0))
        out.extend(ranked[:k])
    return out
