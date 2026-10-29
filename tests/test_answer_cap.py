"""The answer cap (num_predict): truncated replies are flagged, salvaged, counted and logged."""

import json

from clausescout.llm.client import OllamaClient, salvage_items
from clausescout.llm.extractor import LLMExtractor
from clausescout.llm.hybrid import HybridExtractor
from tests.test_hybrid import ASSIGN, LAW, TEXT, StubQA, _scores

CLAUSE = "This Agreement is governed by the laws of Singapore."
WHOLE = {"type": "Governing Law", "quote": CLAUSE, "confidence": "high"}


class CutClient:
    """Returns each reply with the usage Ollama gives when an answer stopped at the cap."""

    def __init__(self, replies):
        self.replies = list(replies)

    def chat(self, system, user, schema=None):
        text = self.replies.pop(0)
        return text, {"input_tokens": 100, "output_tokens": 6144, "cost_usd": 0.0,
                      "truncated": 1, "cap": 6144}


def test_salvage_keeps_whole_items_and_says_when_one_was_cut():
    cut = json.dumps({"clauses": [WHOLE, WHOLE]})[:-30]
    items, lost = salvage_items(cut, "clauses")
    assert items == [WHOLE] and lost
    # A reply cut just after a whole item loses nothing that was started.
    items, lost = salvage_items('{"clauses": [' + json.dumps(WHOLE) + ", ", "clauses")
    assert items == [WHOLE] and not lost
    assert salvage_items("", "clauses") == ([], False)


def test_client_sends_the_cap_only_when_set_and_flags_truncation(monkeypatch):
    import httpx

    class Reply:
        def __init__(self, reason):
            self.data = {"message": {"content": "{}"}, "prompt_eval_count": 10,
                         "eval_count": 5, "done_reason": reason}

        def raise_for_status(self):
            pass

        def json(self):
            return self.data

    sent = []
    replies = iter([Reply("stop"), Reply("length")])
    monkeypatch.setattr(httpx, "post",
                        lambda url, json, timeout: sent.append(json) or next(replies))
    # Without a cap the request is exactly what v1 sent.
    assert OllamaClient(model="m", host="http://x").chat("s", "u")[1]["truncated"] == 0
    assert "num_predict" not in sent[0]["options"]
    capped = OllamaClient(model="m", host="http://x", num_predict=6144)
    assert capped.chat("s", "u")[1]["truncated"] == 1
    assert sent[1]["options"]["num_predict"] == 6144


def test_fit_cap_is_what_the_window_has_left_after_the_prompt(monkeypatch):
    import httpx

    class Reply:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "{}"}, "prompt_eval_count": 4000, "eval_count": 5,
                    "done_reason": "stop"}

    sent = []
    monkeypatch.setattr(httpx, "post", lambda url, json, timeout: sent.append(json) or Reply())
    client = OllamaClient(model="m", host="http://x", num_ctx=6144, num_predict="fit",
                          cap_margin=16)
    # I stand in for the tokenizer, so the test needs no download.
    client.prompt_tokens = lambda system, user: 4000
    usage = client.chat("s", "u")[1]
    assert sent[0]["options"]["num_predict"] == 6144 - 4000 - 16
    assert usage["cap"] == 2128 and usage["prompt_tokens_local"] == 4000
    # A prompt that fills the window still gets a small positive cap, never 0 (no cap).
    client.prompt_tokens = lambda system, user: 6140
    client.chat("s", "u")
    assert sent[1]["options"]["num_predict"] == 64


def test_truncated_llm_reply_keeps_its_whole_findings_and_is_logged(tmp_path):
    log = tmp_path / "requests.jsonl"
    cut = json.dumps({"clauses": [WHOLE, WHOLE]})[:-30]
    ex = LLMExtractor(CutClient([cut]), request_log=log)
    found = ex.extract("c", CLAUSE)
    # The cut reply still gives its whole finding, and is counted as truncated, not as bad JSON.
    assert [f.category for f in found] == ["Governing Law"]
    assert ex.usage["truncated"] == 1 and ex.usage["bad_json"] == 0
    assert ex.usage["salvaged_items"] == 1 and ex.usage["truncated_lost"] == 1
    row = json.loads(log.read_text(encoding="utf-8"))
    assert row["contract_id"] == "c" and row["cap_hit"] and row["maybe_lost"]
    assert row["prompt_tokens"] == 100 and row["output_tokens"] == 6144 and row["items"] == 1


def test_truncated_hybrid_reply_keeps_answered_passages(tmp_path):
    # The reply answers passage 0 in full and is cut inside passage 1.
    cut = '{"passages": [{"id": 0, "types": ["Anti-Assignment"]}, {"id": 1, "types": ["Gov'
    ex = HybridExtractor(CutClient([cut]), StubQA(), request_log=tmp_path / "r.jsonl")
    s = _scores(ex.extract("c", TEXT))
    assert s[("Anti-Assignment", ASSIGN[0])] == 0.8      # confirmed from the salvaged item
    assert s[("Governing Law", LAW[0])] == 0.3           # unanswered: keeps its QA score
    assert ex.usage["truncated"] == 1 and ex.usage["salvaged_items"] == 1
    row = json.loads((tmp_path / "r.jsonl").read_text(encoding="utf-8"))
    assert row["cap"] == 6144 and row["cap_hit"] and row["batch"] == 0
