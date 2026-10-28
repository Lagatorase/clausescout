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
                 timeout: float = 600):
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
        self.host = (host or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.num_ctx = num_ctx
        self.timeout = timeout

    def chat(self, system: str, user: str, schema: dict | None = None) -> tuple[str, dict]:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "stream": False,
            # Temperature 0 and a fixed seed so prompt versions can be compared fairly.
            "options": {"temperature": 0, "seed": 0, "num_ctx": self.num_ctx},
        }
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


def with_retries(fn, attempts: int = 3, wait: float = 5.0):
    # Local servers occasionally time out on a long chunk, so I retry a couple of times.
    for k in range(attempts):
        try:
            return fn()
        except (httpx.HTTPError, json.JSONDecodeError):
            if k == attempts - 1:
                raise
            time.sleep(wait * (k + 1))
