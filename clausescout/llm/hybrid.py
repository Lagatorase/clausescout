"""The hybrid method: the fine-tuned QA model finds passages, the local LLM checks them.

QA models are good at finding the right part of a contract but are easily fooled by text that
looks like a clause type. An LLM reads more carefully but is slow and can invent text. So I let
the QA model propose candidate passages (anything above a low probability), and ask the LLM which
clause types each passage really is. Because every quote is a QA span taken straight from the
contract, the hybrid cannot invent text.

Scores: a type the LLM confirms gets 0.5 + 0.5 * the QA probability, a type it rejects keeps
only a fifth of its QA probability (so the ranking still has it, far down), and a type the LLM
adds that the QA model didn't propose for that passage gets 0.5.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from clausescout.data.cuad import CATEGORIES
from clausescout.findings import Finding
from clausescout.llm.client import with_retries
from clausescout.llm.extractor import PROMPT_DIR, category_descriptions


def hybrid_schema(categories: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "passages": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "types": {"type": "array", "items": {"type": "string", "enum": categories}},
                    },
                    "required": ["id", "types"],
                },
            }
        },
        "required": ["passages"],
    }


def load_findings(path: str | Path) -> dict[str, list[Finding]]:
    """Saved findings from an earlier run (runs/<name>/findings.jsonl), grouped by contract."""
    out: dict[str, list[Finding]] = defaultdict(list)
    with open(path, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            out[d["contract_id"]].append(Finding(**d))
    return out


class HybridExtractor:
    def __init__(self, client, candidates, prompt_version: str = "hybrid-v1",
                 min_prob: float = 0.05, batch: int = 15, max_passage_chars: int = 1500):
        """candidates is a QA extractor (run live) or a path to saved QA findings."""
        self.client = client
        self.name = f"hybrid-{prompt_version}"
        if isinstance(candidates, (str, Path)):
            self._saved, self._qa = load_findings(candidates), None
        else:
            self._saved, self._qa = None, candidates
        descriptions = category_descriptions()
        listing = "\n".join(f"- {c}: {descriptions[c]}" for c in CATEGORIES)
        template = (PROMPT_DIR / f"{prompt_version}.md").read_text(encoding="utf-8")
        self.system = template.format(categories=listing)
        self.schema = hybrid_schema(list(CATEGORIES))
        self.min_prob, self.batch, self.max_chars = min_prob, batch, max_passage_chars
        self.usage = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "calls": 0,
                      "bad_json": 0, "passages": 0}

    def _candidates(self, contract_id: str, text: str) -> list[Finding]:
        if self._qa is not None:
            found = self._qa.extract(contract_id, text)
        else:
            found = self._saved.get(contract_id, [])
        return [f for f in found if f.score >= self.min_prob]

    def _ask(self, passages: list[tuple[str, list[str]]]) -> dict[int, list[str]]:
        lines = []
        for i, (text, suggested) in enumerate(passages):
            lines.append(f"[{i}] (suggested: {', '.join(suggested)})\n{text[:self.max_chars]}")
        reply, usage = with_retries(
            lambda: self.client.chat(self.system, "\n\n".join(lines), self.schema))
        for k in ("input_tokens", "output_tokens", "cost_usd"):
            self.usage[k] += usage.get(k, 0)
        self.usage["calls"] += 1
        try:
            items = json.loads(reply).get("passages", [])
        except (json.JSONDecodeError, AttributeError):
            self.usage["bad_json"] += 1
            return {}
        return {int(i["id"]): [t for t in i.get("types", []) if t in CATEGORIES]
                for i in items if isinstance(i, dict) and "id" in i}

    def extract(self, contract_id: str, text: str) -> list[Finding]:
        # The same span is often proposed for several types, so I ask about each span once.
        spans: dict[tuple[int, int], dict[str, float]] = defaultdict(dict)
        for f in self._candidates(contract_id, text):
            if f.start is None or f.end is None:
                continue
            probs = spans[(f.start, f.end)]
            probs[f.category] = max(probs.get(f.category, 0.0), f.score)
        keys = sorted(spans, key=lambda k: -max(spans[k].values()))
        self.usage["passages"] += len(keys)
        out = []
        for b in range(0, len(keys), self.batch):
            chunk = keys[b:b + self.batch]
            answers = self._ask([(text[s:e], sorted(spans[(s, e)])) for s, e in chunk])
            for i, (s, e) in enumerate(chunk):
                qa_probs = spans[(s, e)]
                # If the LLM's reply skipped a passage, I fall back to the QA scores unchanged.
                confirmed = set(answers[i]) if i in answers else None
                for cat in CATEGORIES:
                    p = qa_probs.get(cat)
                    if confirmed is None:
                        score = p
                    elif cat in confirmed:
                        score = 0.5 + 0.5 * p if p is not None else 0.5
                    else:
                        score = 0.2 * p if p is not None else None
                    if score is not None:
                        out.append(Finding(contract_id, cat, text[s:e], score, s, e, self.name))
        return out
