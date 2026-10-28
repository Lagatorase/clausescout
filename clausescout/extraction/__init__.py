"""Clause extraction methods, built by name from experiments.yaml."""

from __future__ import annotations


def build_method(method: str, params: dict | None = None):
    """Creates an extractor from its config name. Imports are lazy so CPU-only runs stay light."""
    params = params or {}
    if method == "keywords":
        from clausescout.extraction.keywords import KeywordExtractor

        return KeywordExtractor(**params)
    if method == "qa":
        from clausescout.models.qa import QAExtractor

        return QAExtractor(**params)
    if method == "llm":
        from clausescout.llm.client import build_client
        from clausescout.llm.extractor import LLMExtractor

        # Client settings (backend, model, context size) and extractor settings share one dict.
        client_keys = {"backend", "model", "num_ctx"}
        client = build_client(**{k: v for k, v in params.items() if k in client_keys})
        return LLMExtractor(client, **{k: v for k, v in params.items() if k not in client_keys})
    raise ValueError(f"Unknown method {method!r}")
