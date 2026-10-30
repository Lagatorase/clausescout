"""Shared test setup."""

import os
from pathlib import Path

# The app defaults to the fine-tuned QA model, which isn't in CI, so I point the API tests at
# the keyword config, which needs no model.
os.environ.setdefault(
    "CLAUSESCOUT_CONFIG", str(Path(__file__).resolve().parents[1] / "config" / "app-keywords.yaml"))
