"""Running one extraction method over a set of contracts and scoring it the same way every time.

Every method goes through the same steps here, so the numbers in the report are comparable:
extract, ground every span against the contract, time it, add up any API cost, then compute
the span-level (CUAD) and contract-level metrics on the grounded findings only.
"""

from __future__ import annotations

import ctypes
import json
import os
import platform
import subprocess
import time
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path

from clausescout.data.cuad import CATEGORIES, HIGH_STAKES, Contract
from clausescout.findings import MAX_PER_TYPE, Finding, to_preds, top_per_type
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
    contracts: list[Contract], findings: list[Finding], threshold: float, n_boot: int = 0,
    max_per_type: int | None = MAX_PER_TYPE,
) -> dict:
    """The metric part of a results file, so saved findings can be re-scored without re-running.

    Span metrics use every finding, as in the CUAD paper. Contract metrics use what a reviewer
    would see: at most max_per_type quotes per clause type, then the threshold.
    """
    gold = gold_from_contracts(contracts, CATEGORIES)
    span = span_metrics(gold, to_preds(findings), n_boot=n_boot)
    shown = top_per_type(findings, max_per_type)
    con = contract_metrics(gold, to_preds(shown), threshold=threshold, n_boot=n_boot)
    n_shown = sum(f.score >= threshold for f in shown)

    def per_cat(name):
        s, p = span.per_category[name], con.per_category[name]
        return {"span": asdict(s), "contract": asdict(p)}

    return {
        "threshold": threshold,
        "max_per_type": max_per_type,
        # How much a reviewer has to read: quotes shown per contract after the cap and threshold.
        "findings_per_contract": n_shown / max(len(contracts), 1),
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
    max_per_type: int | None = MAX_PER_TYPE,
    progress: bool = False,
    resume_path: str | os.PathLike | None = None,
) -> tuple[dict, list[Finding]]:
    """Scores one method on some contracts. Returns a JSON-ready summary and the kept findings.

    method needs an extract(contract_id, text) -> list[Finding] method. It may also have a
    usage dict (input_tokens, output_tokens, cost_usd) that grows as it runs, for paid APIs.

    With resume_path, each contract's raw output, time and usage are appended to that file as
    soon as it finishes, and contracts already in it are not run again. A long run that gets
    stopped then loses at most one contract.
    """
    contracts = list(contracts)
    kept_all: list[Finding] = []
    stats = GroundingStats()
    seconds = []
    done: dict[str, dict] = {}
    if resume_path and Path(resume_path).exists():
        with open(resume_path, encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                done[row["contract_id"]] = row
    usage_extra: dict[str, float] = {}
    for k, c in enumerate(contracts, 1):
        if c.id in done:
            # Saved by an earlier, interrupted run: reuse its raw output, time and usage.
            row = done[c.id]
            raw = [Finding(**f) for f in row["raw"]]
            elapsed = row["seconds"]
            for key, v in row["usage"].items():
                usage_extra[key] = usage_extra.get(key, 0) + v
        else:
            before = dict(getattr(method, "usage", {}) or {})
            t0 = time.perf_counter()
            raw = method.extract(c.id, c.text)
            elapsed = time.perf_counter() - t0
            if resume_path:
                after = dict(getattr(method, "usage", {}) or {})
                used = {key: v - before.get(key, 0) for key, v in after.items()
                        if isinstance(v, int | float)}
                with open(resume_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"contract_id": c.id, "seconds": elapsed, "usage": used,
                                        "raw": [asdict(x) for x in raw]}) + "\n")
        # I pass each finding's own offset as a hint, so repeated text keeps the right place.
        kept, s = ground_findings(raw, c.text, GroundingIndex(c.text), hints=[f.start for f in raw])
        seconds.append(elapsed)
        kept_all.extend(kept)
        stats = stats + s
        if progress:
            print(f"\r  {k}/{len(contracts)} contracts, {sum(seconds):.0f}s", end="", flush=True)
    if progress:
        print()

    usage = dict(getattr(method, "usage", {}) or {})
    for key, v in usage_extra.items():
        usage[key] = usage.get(key, 0) + v
    n = len(contracts)
    summary = {
        "contracts": n,
        **score_findings(contracts, kept_all, threshold, n_boot, max_per_type),
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
