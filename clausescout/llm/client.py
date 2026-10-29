"""Small LLM clients with one interface: chat(system, user, schema) -> (text, usage).

Local Ollama is the default. Hosted backends are only built when ALLOW_HOSTED_LLM is true, so a
contract can't leave the machine by accident.
"""

from __future__ import annotations

import json
import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()


class OllamaClient:
    def __init__(self, model: str | None = None, host: str | None = None, num_ctx: int = 8192,
                 timeout: float = 600, num_predict: int | str | None = None,
                 cap_margin: int = 16, tokenizer: str = "Qwen/Qwen2.5-7B-Instruct"):
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
        self.host = (host or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.num_ctx = num_ctx
        self.timeout = timeout
        # A cap on answer length. Without one, an answer that never closes its JSON can run until
        # the request times out (llm-qwen7b-v1 did, three times, on one validation contract).
        # "fit" caps each answer at what is left of the window after its prompt, minus a margin,
        # so an answer that fits is never cut and a runaway one stops when the window is full.
        self.num_predict, self.cap_margin = num_predict, cap_margin
        self.tokenizer_name, self._tokenizer = tokenizer, None

    def prompt_tokens(self, system: str, user: str) -> int:
        """The prompt's length in tokens, counted the way Ollama counts it.

        Ollama can't count tokens before a request, so I use the model's own tokenizer and chat
        template. On v1's 154 requests this matched Ollama's prompt_eval_count exactly.
        """
        if self._tokenizer is None:
            from transformers import AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(self.tokenizer_name)
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        text = self._tokenizer.apply_chat_template(messages, add_generation_prompt=True,
                                                   tokenize=False)
        return len(self._tokenizer(text, add_special_tokens=False)["input_ids"])

    def cap_for(self, system: str, user: str) -> tuple[int | None, int | None]:
        """(answer cap to send, local prompt token count) for one request."""
        if self.num_predict != "fit":
            return self.num_predict, None
        n = self.prompt_tokens(system, user)
        # A prompt that leaves almost no room still gets a short answer rather than none (and a
        # cap of 0 or less would mean no cap at all to Ollama).
        return max(self.num_ctx - n - self.cap_margin, 64), n

    def chat(self, system: str, user: str, schema: dict | None = None) -> tuple[str, dict]:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "stream": False,
            # Temperature 0 and a fixed seed so prompt versions can be compared fairly.
            "options": {"temperature": 0, "seed": 0, "num_ctx": self.num_ctx},
        }
        cap, local_prompt = self.cap_for(system, user)
        # I only send the cap when one is set, so runs without it send exactly what v1 sent.
        if cap is not None:
            body["options"]["num_predict"] = cap
        if schema is not None:
            # Ollama constrains the output to this JSON schema.
            body["format"] = schema
        r = httpx.post(f"{self.host}/api/chat", json=body, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        usage = {"input_tokens": data.get("prompt_eval_count", 0),
                 "output_tokens": data.get("eval_count", 0), "cost_usd": 0.0}
        # The context window is kept small to save memory, so I count any request that filled
        # it: its input may have been cut or its answer stopped early.
        usage["context_full"] = int(usage["input_tokens"] + usage["output_tokens"] >= self.num_ctx)
        # Ollama says "length" when the answer stopped at the cap rather than ending by itself.
        usage["truncated"] = int(data.get("done_reason") == "length")
        usage["cap"], usage["prompt_tokens_local"] = cap, local_prompt
        return data["message"]["content"], usage


class StubClient:
    """Returns canned replies in order, for tests. Records what it was asked."""

    def __init__(self, replies: list[str | dict]):
        self.replies = list(replies)
        self.calls: list[tuple[str, str]] = []

    def chat(self, system: str, user: str, schema: dict | None = None) -> tuple[str, dict]:
        self.calls.append((system, user))
        reply = self.replies.pop(0) if self.replies else {"clauses": []}
        text = reply if isinstance(reply, str) else json.dumps(reply)
        return text, {"input_tokens": len(user) // 4, "output_tokens": len(text) // 4,
                      "cost_usd": 0.0}


def build_client(backend: str | None = None, **kwargs):
    backend = backend or os.getenv("LLM_BACKEND", "ollama")
    if backend == "ollama":
        return OllamaClient(**kwargs)
    if os.getenv("ALLOW_HOSTED_LLM", "false").lower() != "true":
        raise RuntimeError(f"Backend {backend!r} sends text off this machine; set "
                           "ALLOW_HOSTED_LLM=true to allow it.")
    raise NotImplementedError(f"Backend {backend!r} is added at the hosted LLM checkpoint.")


def salvage_items(text: str, key: str) -> tuple[list[dict], bool]:
    """The complete items of a JSON reply {key: [{...}, ...]} that was cut off part way.

    Returns the items that parsed whole, and whether anything was left after the last of them
    (a half-written item, so at least one answer may be lost).
    """
    start = text.find("[", max(text.find(f'"{key}"'), 0))
    if start == -1:
        return [], bool(text.strip())
    decoder, items, pos = json.JSONDecoder(), [], start + 1
    while True:
        # Skip the whitespace and commas between items.
        while pos < len(text) and text[pos] in " \t\r\n,":
            pos += 1
        if pos >= len(text) or text[pos] == "]":
            return items, False
        try:
            item, pos = decoder.raw_decode(text, pos)
        except json.JSONDecodeError:
            return items, True
        if isinstance(item, dict):
            items.append(item)


def with_retries(fn, attempts: int = 3, wait: float = 5.0):
    # Local servers occasionally time out on a long chunk, so I retry a couple of times.
    for k in range(attempts):
        try:
            return fn()
        except (httpx.HTTPError, json.JSONDecodeError):
            if k == attempts - 1:
                raise
            time.sleep(wait * (k + 1))
