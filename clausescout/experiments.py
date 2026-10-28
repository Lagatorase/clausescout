"""Running one extraction method over a set of contracts and scoring it the same way every time.

Every method goes through the same steps here, so the numbers in the report are comparable:
extract, ground every span against the contract, time it, add up any API cost, then compute
the span-level (CUAD) and contract-level metrics on the grounded findings only.
"""

from __future__ import annotations

import ctypes
import os
import platform
import subprocess
import time
from collections.abc import Iterable
from dataclasses import asdict

from clausescout.data.cuad import CATEGORIES, HIGH_STAKES, Contract
from clausescout.findings import Finding, to_preds
from clausescout.grounding.verbatim import GroundingIndex, GroundingStats, ground_findings
from clausescout.metrics.contract import contract_metrics
from clausescout.metrics.span import gold_from_contracts, span_metrics


def hardware() -> dict:
    """What the run used, so time per contract can be read in context."""
    info = {"platform": platform.platform(), "cpu": platform.processor(), "ram_gb": None,
            "gpu": None}
    if os.name == "nt":
        # GlobalMemoryStatusEx is the simplest way to read total RAM on Windows without psutil.
        class _Mem(ctypes.Structure):
            _fields_ = [("len", ctypes.c_ulong), ("load", ctypes.c_ulong),
                        ("total", ctypes.c_ulonglong), ("avail", ctypes.c_ulonglong),
                        ("pt", ctypes.c_ulonglong), ("pa", ctypes.c_ulonglong),
                        ("vt", ctypes.c_ulonglong), ("va", ctypes.c_ulonglong),
                        ("vx", ctypes.c_ulonglong)]
        m = _Mem()
        m.len = ctypes.sizeof(_Mem)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
            info["ram_gb"] = round(m.total / 2**30, 1)
    elif hasattr(os, "sysconf"):
        info["ram_gb"] = round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30, 1)
    try:
        import torch

        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            info["gpu"] = f"{props.name} ({props.total_memory / 2**30:.1f} GB)"
    except ImportError:
        pass
    return info


def git_commit() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                             text=True, check=True)
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def score_findings(
    contracts: list[Contract], findings: list[Finding], threshold: float, n_boot: int = 0
) -> dict:
    """The metric part of a results file, so saved findings can be re-scored without re-running."""
    gold = gold_from_contracts(contracts, CATEGORIES)
    preds = to_preds(findings)
    span = span_metrics(gold, preds, n_boot=n_boot)
    con = contract_metrics(gold, preds, threshold=threshold, n_boot=n_boot)

    def per_cat(name):
        s, p = span.per_category[name], con.per_category[name]
        return {"span": asdict(s), "contract": asdict(p)}

    return {
        "threshold": threshold,
        "span": {"overall": asdict(span.overall), "macro_aupr": span.macro_aupr},
        "contract": {"micro": asdict(con.micro), "macro": con.macro,
                     "high_stakes": con.high_stakes, "macro_ci": con.macro_ci,
                     "high_stakes_ci": con.high_stakes_ci},
        "per_category": {cat: per_cat(cat) for cat in CATEGORIES if cat in span.per_category},
        "high_stakes_types": HIGH_STAKES,
    }


def run_experiment(
    method,
    contracts: Iterable[Contract],
    threshold: float = 0.5,
    n_boot: int = 0,
    progress: bool = False,
) -> tuple[dict, list[Finding]]:
    """Scores one method on some contracts. Returns a JSON-ready summary and the kept findings.

    method needs an extract(contract_id, text) -> list[Finding] method. It may also have a
    usage dict (input_tokens, output_tokens, cost_usd) that grows as it runs, for paid APIs.
    """
    contracts = list(contracts)
    kept_all: list[Finding] = []
    stats = GroundingStats()
    seconds = []
    for k, c in enumerate(contracts, 1):
        t0 = time.perf_counter()
        raw = method.extract(c.id, c.text)
        # I pass each finding's own offset as a hint, so repeated text keeps the right place.
        kept, s = ground_findings(raw, c.text, GroundingIndex(c.text), hints=[f.start for f in raw])
        seconds.append(time.perf_counter() - t0)
        kept_all.extend(kept)
        stats = stats + s
        if progress:
            print(f"\r  {k}/{len(contracts)} contracts, {sum(seconds):.0f}s", end="", flush=True)
    if progress:
        print()

    usage = dict(getattr(method, "usage", {}) or {})
    n = len(contracts)
    summary = {
        "contracts": n,
        **score_findings(contracts, kept_all, threshold, n_boot),
        "grounding": {
            "submitted": stats.submitted, "accepted": stats.accepted, "rejected": stats.rejected,
            "rejection_rate": stats.rejection_rate,
            "rejected_examples": [
                {"contract": f.contract_id, "category": f.category, "text": f.text[:500]}
                for f in stats.rejected_examples[:20]
            ],
        },
        "time": {"total_s": sum(seconds), "per_contract_s": sum(seconds) / max(n, 1),
                 "max_contract_s": max(seconds, default=0.0)},
        "usage": usage,
        "cost_per_contract_usd": usage.get("cost_usd", 0.0) / max(n, 1),
        "hardware": hardware(),
        "git_commit": git_commit(),
    }
    return summary, kept_all
