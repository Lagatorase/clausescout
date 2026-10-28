"""The review pipeline the app runs on one document: extract, ground, threshold, flag."""

from __future__ import annotations

from dataclasses import dataclass

from clausescout.data.documents import Document
from clausescout.grounding.verbatim import GroundingIndex, GroundingStats, ground_findings
from clausescout.playbook.engine import Rule, apply_playbook
from clausescout.report.export import ContractReview


@dataclass
class ReviewResult:
    review: ContractReview
    grounding: GroundingStats
    text: str


def review_document(doc: Document, method, threshold: float, rules: list[Rule]) -> ReviewResult:
    """Runs one extraction method over a document and turns the result into a review."""
    raw = method.extract(doc.name, doc.text)
    # Grounding drops anything that is not word for word in the document, the same check the
    # evaluation uses, so the app never shows a quote that isn't really there.
    kept, stats = ground_findings(raw, doc.text, GroundingIndex(doc.text),
                                  hints=[f.start for f in raw])
    kept = [f for f in kept if f.score >= threshold]
    # Repeated quotes for the same clause type add nothing for the reader, so I keep the best.
    best = {}
    for f in kept:
        key = (f.category, f.start, f.end)
        if key not in best or f.score > best[key].score:
            best[key] = f
    findings = sorted(best.values(), key=lambda f: (f.start or 0, -f.score))
    flags = apply_playbook(rules, findings, doc.text)
    review = ContractReview(doc.name, findings, flags, doc.segments)
    return ReviewResult(review, stats, doc.text)
