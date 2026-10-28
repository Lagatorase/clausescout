"""QA windowing and feature building, with a fake whitespace tokenizer so no model is needed."""

import re

from clausescout.data.cuad import CATEGORIES, Contract, Span
from clausescout.models import qa


class FakeTokenizer:
    """One token per word, ids from a growing vocabulary, offsets like a fast tokenizer."""

    cls_token_id, sep_token_id, pad_token_id = 1, 2, 0

    def __init__(self):
        self.vocab = {}

    def __call__(self, text, add_special_tokens=False, return_offsets_mapping=False):
        spans = [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]
        ids = [self.vocab.setdefault(text[a:b], len(self.vocab) + 3) for a, b in spans]
        out = {"input_ids": ids}
        if return_offsets_mapping:
            out["offset_mapping"] = spans
        return out


def _windows(monkeypatch, max_len=40, stride=10):
    monkeypatch.setattr(qa, "MAX_LEN", max_len)
    monkeypatch.setattr(qa, "STRIDE", stride)
    questions = {"Governing Law": "Which law governs?", "Parties": "Who are the parties?"}
    return qa.Windows(FakeTokenizer(), questions)


def test_windows_cover_every_token_with_overlap(monkeypatch):
    w = _windows(monkeypatch)
    text = " ".join(f"w{i}" for i in range(100))
    enc = w.encode(text)
    covered = set()
    for s in enc.starts:
        covered.update(range(s, min(s + w.ctx_len, 100)))
    assert covered == set(range(100))
    ids, ctx = w.build(enc, 1, "Parties")
    assert ids[0] == 1 and ids[ctx - 1] == 2 and ids[-1] == 2
    assert len(ids) <= qa.MAX_LEN


def test_char_to_token_span():
    enc = qa.Encoded([5, 6, 7, 8], [(0, 3), (4, 9), (10, 12), (13, 20)], [0])
    assert qa.char_to_token_span(enc, 4, 12) == (1, 2)
    # A span starting mid-token still includes that token.
    assert qa.char_to_token_span(enc, 6, 20) == (1, 3)


def test_training_features_label_answers_and_balance_negatives(monkeypatch):
    w = _windows(monkeypatch)
    words = [f"w{i}" for i in range(200)]
    law = "governed by Singapore law"
    words[50:54] = law.split()
    text = " ".join(words)
    c = Contract("c", text, {cat: [] for cat in CATEGORIES})
    c.labels["Governing Law"] = [Span(law, text.index(law))]
    encoded, rows, counts = qa.training_features(w, [c], seed=0, neg_ratio=1.0)
    data = qa.FeatureDataset(w, encoded, rows)
    positives = [data[i] for i, r in enumerate(rows) if r[3] >= 0]
    assert counts["positives"] == len(positives) >= 1
    words_of = {i: word for word, i in w.tok.vocab.items()}
    for ids, start, end in positives:
        # The labelled tokens decode to exactly the answer's words.
        assert [words_of[i] for i in ids[start:end + 1]] == law.split()
    # Negatives are downsampled to roughly match the positives.
    assert counts["negatives"] <= 4 * counts["positives"] + 4
    batch = qa.collate([data[i] for i in range(len(rows))], pad_id=0)
    assert batch["input_ids"].shape[0] == len(rows)
