"""The LLM method: ask a chat model for every clause type in each chunk of a contract.

I split the contract into overlapping chunks so a clause cut at one chunk's edge is whole in the
next, ask for all clause types at once in a strict JSON schema with verbatim quotes, and merge
the answers. The grounding check in the experiment runner then throws out any quote that isn't
really in the contract, and counts it.
"""

from __future__ import annotations

import json
from pathlib import Path

from clausescout.data.cuad import CATEGORIES
from clausescout.findings import Finding
from clausescout.grounding.verbatim import normalise
from clausescout.llm.client import with_retries

PROMPT_DIR = Path(__file__).parent / "prompts"
CONFIDENCE = {"high": 0.9, "medium": 0.6, "low": 0.3}


def category_descriptions() -> dict[str, str]:
    """A one-line description per type, taken from the "Details:" part of CUAD's questions."""
    path = Path(__file__).parent / "category_descriptions.json"
    return json.loads(path.read_text(encoding="utf-8"))


def response_schema(categories: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "clauses": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": categories},
                        "quote": {"type": "string"},
                        "confidence": {"type": "string", "enum": list(CONFIDENCE)},
                    },
                    "required": ["type", "quote", "confidence"],
                },
            }
        },
        "required": ["clauses"],
    }


def chunks(text: str, size: int, overlap: int) -> list[tuple[int, int]]:
    """Character ranges of about size characters that overlap by about overlap characters.

    I end each chunk at a line break where I can, so clauses are less often cut mid-sentence.
    """
    out, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            cut = text.rfind("\n", start + size // 2, end)
            if cut != -1:
                end = cut + 1
        out.append((start, end))
        if end >= len(text):
            break
        # The next chunk starts overlap characters back, at the start of a line if possible.
        nxt = max(end - overlap, start + 1)
        line = text.find("\n", nxt, end)
        start = line + 1 if line != -1 else nxt
    return out


class LLMExtractor:
    def __init__(self, client, prompt_version: str = "v1", chunk_chars: int = 12000,
                 overlap_chars: int = 1500, categories: list[str] | None = None):
        self.client = client
        self.prompt_version = prompt_version
        self.name = f"llm-{prompt_version}"
        self.categories = categories or list(CATEGORIES)
        descriptions = category_descriptions()
        listing = "\n".join(f"- {c}: {descriptions[c]}" for c in self.categories)
        template = (PROMPT_DIR / f"{prompt_version}.md").read_text(encoding="utf-8")
        self.system = template.format(categories=listing)
        self.schema = response_schema(self.categories)
        self.chunk_chars, self.overlap_chars = chunk_chars, overlap_chars
        self.usage = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "calls": 0,
                      "bad_json": 0, "unknown_type": 0}

    def _ask(self, excerpt: str) -> list[dict]:
        text, usage = with_retries(lambda: self.client.chat(self.system, excerpt, self.schema))
        for k in ("input_tokens", "output_tokens", "cost_usd"):
            self.usage[k] += usage.get(k, 0)
        self.usage["calls"] += 1
        try:
            items = json.loads(text).get("clauses", [])
        except (json.JSONDecodeError, AttributeError):
            # A broken reply loses this chunk; I count it rather than hide it.
            self.usage["bad_json"] += 1
            return []
        return [i for i in items if isinstance(i, dict)]

    def extract(self, contract_id: str, text: str) -> list[Finding]:
        best: dict[tuple[str, str], Finding] = {}
        for start, end in chunks(text, self.chunk_chars, self.overlap_chars):
            for item in self._ask(text[start:end]):
                cat, quote = item.get("type"), str(item.get("quote", "")).strip()
                if cat not in self.categories:
                    self.usage["unknown_type"] += 1
                    continue
                if not quote:
                    continue
                score = CONFIDENCE.get(item.get("confidence"), 0.3)
                # The chunk start is a hint for where repeated text should be placed.
                f = Finding(contract_id, cat, quote, score, start, None, self.name)
                # Overlapping chunks often return the same quote twice; I keep the surer one.
                key = (cat, normalise(quote))
                if key not in best or best[key].score < score:
                    best[key] = f
        return list(best.values())
