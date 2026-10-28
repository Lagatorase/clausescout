"""Extractive question answering over long contracts, as in the CUAD paper.

Each clause type is a question ("Highlight the parts (if any) of this contract related to ...").
A contract is far longer than the model's 512 tokens, so I slide a window over it. I tokenise
each contract once and reuse the same windows for all 41 questions, which keeps feature
building cheap: a training feature is just (contract, window, question, start, end) and the
token ids are only put together when a batch is made.

At inference I follow the post-processing behind CUAD's nbest_predictions.json: for each
contract and question I gather the best start/end pairs from every window, keep the top 20 by
start + end logit, add the null answer (the best "no answer" score over the windows), and turn
the scores into probabilities with a softmax over that list.
"""

from __future__ import annotations

import bisect
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch

from clausescout.data.cuad import CATEGORIES, MASTER_JSON, Contract
from clausescout.findings import Finding

MAX_LEN = 512
MAX_QUESTION = 64
STRIDE = 256
N_BEST = 20
MAX_ANSWER_TOKENS = 400


def cuad_questions(path: Path = MASTER_JSON) -> dict[str, str]:
    """The question CUAD asks for each category, read from the dataset's own JSON."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))["data"][0]["paragraphs"][0]["qas"]
    return {qa["id"].split("__", 1)[1]: qa["question"] for qa in data}


@dataclass
class Encoded:
    """One contract tokenised once, with its window start positions."""
    ids: list[int]
    offsets: list[tuple[int, int]]
    starts: list[int]

    def __post_init__(self):
        # Separate start and end lists, kept once per contract for binary search.
        self.tok_starts = [a for a, _ in self.offsets]
        self.tok_ends = [b for _, b in self.offsets]


class Windows:
    def __init__(self, tokenizer, questions: dict[str, str]):
        self.tok = tokenizer
        self.categories = [c for c in CATEGORIES if c in questions]
        self.q_ids = {
            c: tokenizer(questions[c], add_special_tokens=False)["input_ids"][:MAX_QUESTION]
            for c in self.categories
        }
        # Every window uses the same context length, so windows don't depend on the question.
        self.ctx_len = MAX_LEN - 3 - max(len(q) for q in self.q_ids.values())

    def encode(self, text: str) -> Encoded:
        enc = self.tok(text, add_special_tokens=False, return_offsets_mapping=True)
        n = len(enc["input_ids"])
        starts = list(range(0, max(n - self.ctx_len, 0) + 1, STRIDE))
        # I make sure the last tokens are covered by a final window.
        if starts[-1] + self.ctx_len < n:
            starts.append(n - self.ctx_len)
        return Encoded(enc["input_ids"], enc["offset_mapping"], starts)

    def build(self, enc: Encoded, window: int, category: str) -> tuple[list[int], int]:
        """Token ids for one (window, question) pair and where the context starts in them."""
        q = self.q_ids[category]
        s = enc.starts[window]
        ids = [self.tok.cls_token_id, *q, self.tok.sep_token_id,
               *enc.ids[s:s + self.ctx_len], self.tok.sep_token_id]
        return ids, len(q) + 2


def char_to_token_span(enc: Encoded, start: int, end: int) -> tuple[int, int] | None:
    """The first and last token of a character span, found by binary search on the offsets."""
    # The first token that ends after the span starts, and the last that starts before it ends.
    first = bisect.bisect_right(enc.tok_ends, start)
    last = bisect.bisect_left(enc.tok_starts, end) - 1
    if first >= len(enc.offsets) or last < first:
        return None
    return first, last


def training_features(windows: Windows, contracts: list[Contract], seed: int = 0,
                      neg_ratio: float = 1.0):
    """Encodes the contracts and samples balanced (contract, window, category, start, end) rows.

    Positives: one row per gold answer per window that holds it completely. Answers cut by a
    window edge are left out of that window rather than being taught as "no answer". Negatives:
    windows with no answer for the question, downsampled so there are about neg_ratio
    negatives per positive, as the paper balanced them.
    """
    rng = random.Random(seed)
    encoded, pos, neg = [], [], []
    for ci, c in enumerate(contracts):
        enc = windows.encode(c.text)
        encoded.append(enc)
        for cat in windows.categories:
            spans = [char_to_token_span(enc, s.start, s.end) for s in c.labels.get(cat, [])]
            spans = [s for s in spans if s is not None]
            for w, ws in enumerate(enc.starts):
                inside = [(a - ws, b - ws) for a, b in spans
                          if a >= ws and b < ws + windows.ctx_len]
                cut = any(a < ws + windows.ctx_len and b >= ws for a, b in spans)
                if inside:
                    pos.extend((ci, w, cat, a, b) for a, b in inside)
                elif not cut:
                    neg.append((ci, w, cat, -1, -1))
    keep = min(1.0, neg_ratio * len(pos) / max(len(neg), 1))
    neg = [r for r in neg if rng.random() < keep]
    rows = pos + neg
    rng.shuffle(rows)
    return encoded, rows, {"positives": len(pos), "negatives": len(neg)}


class FeatureDataset(torch.utils.data.Dataset):
    def __init__(self, windows: Windows, encoded: list[Encoded], rows: list[tuple]):
        self.windows, self.encoded, self.rows = windows, encoded, rows

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, i: int):
        ci, w, cat, a, b = self.rows[i]
        ids, ctx = self.windows.build(self.encoded[ci], w, cat)
        # No-answer rows point at [CLS], position 0, like SQuAD 2.0.
        start, end = (a + ctx, b + ctx) if a >= 0 else (0, 0)
        return ids, start, end


def collate(batch, pad_id: int):
    n = max(len(ids) for ids, _, _ in batch)
    input_ids = torch.full((len(batch), n), pad_id, dtype=torch.long)
    mask = torch.zeros((len(batch), n), dtype=torch.long)
    for k, (ids, _, _) in enumerate(batch):
        input_ids[k, :len(ids)] = torch.tensor(ids)
        mask[k, :len(ids)] = 1
    starts = torch.tensor([s for _, s, _ in batch])
    ends = torch.tensor([e for _, _, e in batch])
    return {"input_ids": input_ids, "attention_mask": mask,
            "start_positions": starts, "end_positions": ends}


def _softmax(scores: list[float]) -> list[float]:
    m = max(scores)
    exps = [math.exp(s - m) for s in scores]
    total = sum(exps)
    return [e / total for e in exps]


class QAExtractor:
    """Runs a fine-tuned QA model over every window and question of a contract."""

    name = "qa"

    def __init__(self, model_dir: str | Path, batch_size: int = 64, device: str | None = None,
                 categories: list[str] | None = None):
        from transformers import AutoModelForQuestionAnswering, AutoTokenizer

        model_dir = Path(model_dir)
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.tok = AutoTokenizer.from_pretrained(model_dir)
        self.model = AutoModelForQuestionAnswering.from_pretrained(model_dir).to(self.device)
        self.model.eval()
        questions = json.loads((model_dir / "questions.json").read_text(encoding="utf-8"))
        if categories:
            questions = {c: q for c, q in questions.items() if c in categories}
        self.windows = Windows(self.tok, questions)
        self.batch_size = batch_size

    @torch.inference_mode()
    def _logits(self, enc: Encoded, pairs: list[tuple[int, str]]):
        # Start and end logits for every (window, category) pair, in batches.
        out = []
        for k in range(0, len(pairs), self.batch_size):
            chunk = [self.windows.build(enc, w, cat) for w, cat in pairs[k:k + self.batch_size]]
            batch = collate([(ids, 0, 0) for ids, _ in chunk], self.tok.pad_token_id)
            with torch.autocast(self.device, dtype=torch.bfloat16, enabled=self.device == "cuda"):
                res = self.model(input_ids=batch["input_ids"].to(self.device),
                                 attention_mask=batch["attention_mask"].to(self.device))
            s = res.start_logits.float().cpu().numpy()
            e = res.end_logits.float().cpu().numpy()
            for j, (ids, ctx) in enumerate(chunk):
                out.append((s[j, :len(ids)], e[j, :len(ids)], ctx, len(ids) - 1))
        return out

    def extract(self, contract_id: str, text: str) -> list[Finding]:
        enc = self.windows.encode(text)
        pairs = [(w, cat) for cat in self.windows.categories for w in range(len(enc.starts))]
        logits = self._logits(enc, pairs)
        by_cat: dict[str, list] = {}
        null: dict[str, float] = {}
        for (w, cat), (s, e, ctx, ctx_end) in zip(pairs, logits, strict=True):
            null[cat] = min(null.get(cat, math.inf), float(s[0] + e[0]))
            # The 20 best starts and ends inside the context, paired up where they make a span.
            top_s = np.argsort(-s[ctx:ctx_end])[:N_BEST] + ctx
            top_e = np.argsort(-e[ctx:ctx_end])[:N_BEST] + ctx
            scores = s[top_s][:, None] + e[top_e][None, :]
            length = top_e[None, :] - top_s[:, None]
            scores[(length < 0) | (length >= MAX_ANSWER_TOKENS)] = -np.inf
            # Only this window's 20 best pairs can make the overall top 20 for the question.
            flat = np.argsort(-scores, axis=None)[:N_BEST]
            ws = enc.starts[w]
            for i, j in zip(*np.unravel_index(flat, scores.shape), strict=True):
                if np.isfinite(scores[i, j]):
                    ta, tb = ws + top_s[i] - ctx, ws + top_e[j] - ctx
                    by_cat.setdefault(cat, []).append((float(scores[i, j]), int(ta), int(tb)))
        findings = []
        for cat, cands in by_cat.items():
            cands.sort(key=lambda x: -x[0])
            seen, best = set(), []
            for score, ta, tb in cands:
                start, end = enc.offsets[ta][0], enc.offsets[tb][1]
                # DeBERTa offsets include the space before a word, so I trim it.
                while start < end and text[start].isspace():
                    start += 1
                key = text[start:end]
                if not key or key in seen:
                    continue
                seen.add(key)
                best.append((score, start, end))
                if len(best) == N_BEST:
                    break
            probs = _softmax([sc for sc, _, _ in best] + [null[cat]])
            for (_, start, end), p in zip(best, probs, strict=False):
                findings.append(Finding(contract_id, cat, text[start:end], p, start, end,
                                        self.name))
        return findings
