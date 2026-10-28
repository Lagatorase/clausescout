"""The one shape every extraction method returns, so metrics, grounding and reports share it."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass


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
