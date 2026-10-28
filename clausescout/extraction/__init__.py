"""Clause extraction methods, built by name from experiments.yaml."""

from __future__ import annotations


def build_method(method: str, params: dict | None = None):
    """Creates an extractor from its config name. Imports are lazy so CPU-only runs stay light."""
    params = params or {}
    if method == "keywords":
        from clausescout.extraction.keywords import KeywordExtractor

        return KeywordExtractor(**params)
    raise ValueError(f"Unknown method {method!r}")
