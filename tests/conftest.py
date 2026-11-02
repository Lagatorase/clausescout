"""Shared test setup."""

import os
from pathlib import Path

# The app defaults to the fine-tuned QA model, which isn't in CI, so I point the API tests at
# the keyword config, which needs no model.
os.environ.setdefault(
    "CLAUSESCOUT_CONFIG", str(Path(__file__).resolve().parents[1] / "config" / "app-keywords.yaml"))

# Tests must never download the model, so the Hugging Face libraries are kept offline. The
# download path is tested with mocks (tests/test_qa_download.py).
os.environ["HF_HUB_OFFLINE"] = "1"
