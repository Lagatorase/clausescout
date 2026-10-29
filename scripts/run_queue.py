"""Run the remaining GPU queue in order, one job at a time, as its own process.

Jobs: the 4-epoch QA validation run, the hybrid (on candidates from the better QA run), the
DeBERTa-v3-base timing run, a second seed of the better QA config (training and validation),
then the qwen2.5:7b run and the hybrid again, both with the answer cap (v2). Every job resumes
from its checkpoint or partial.jsonl and is skipped if it already finished. Each finished
validation run is re-scored under selection rule 2 (scripts/rescore.py). A failed job is
logged and the queue moves on.

Start, stop and finish times go to runs/queue_log.txt, each job's output to runs/<name>/.

Usage: python scripts/run_queue.py [--dry-run] [--min-free-gb 1.5]
"""

import argparse
import json
import subprocess
import sys
import urllib.request
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import yaml

from clausescout.experiments import wait_for_memory

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
RESULTS = ROOT / "experiments" / "results"
QUEUE_LOG = RUNS / "queue_log.txt"
CONFIG = ROOT / "experiments" / "experiments.yaml"
OLLAMA = "http://localhost:11434"


def log(msg: str) -> None:
    # One timestamped line per event, in the log file and on screen.
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    print(line, flush=True)
    RUNS.mkdir(exist_ok=True)
    with open(QUEUE_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(cmd: list[str], out: Path) -> None:
    """Runs one command with its output appended to out; raises if it fails."""
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "a", encoding="utf-8") as f:
        f.write(f"\n=== {datetime.now():%Y-%m-%d %H:%M:%S} {' '.join(cmd)}\n")
        f.flush()
        code = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode
    if code:
        # The last lines of the job's own log usually say what went wrong.
        tail = out.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-3:]
        raise RuntimeError(f"exit code {code}: " + " | ".join(t.strip() for t in tail))


def python(script: str, *args: str) -> list[str]:
    # -u so the job logs show progress as it happens, not when a buffer fills.
    return [sys.executable, "-u", str(ROOT / "scripts" / script), *args]


def rescored(name: str) -> bool:
    """True once a validation run has results re-scored under rule 2."""
    path = RESULTS / f"{name}.json"
    return path.exists() and "threshold_chosen_by" in json.loads(path.read_text(encoding="utf-8"))


def found_f2(name: str) -> float | None:
    """High-stakes found F2 of a finished, re-scored validation run, or None."""
    if not rescored(name):
        return None
    result = json.loads((RESULTS / f"{name}.json").read_text(encoding="utf-8"))
    return result["contract"]["high_stakes"].get("found_f2")


def better_qa(quiet: bool = False) -> str:
    """The QA config (1 or 4 epochs, seed 0) with the higher high-stakes found F2."""
    scores = {n: found_f2(n) for n in ("qa-small-e1-s0", "qa-small-e4-s0")}
    scores = {n: s for n, s in scores.items() if s is not None}
    if not scores:
        raise RuntimeError("neither QA run has results")
    best = max(scores, key=scores.get)
    if not quiet:
            log(f"Better QA run on validation: {best} "
            f"({', '.join(f'{n} {s:.3f}' for n, s in scores.items())})")
    return best


def unload_ollama() -> None:
    # Ollama keeps the model in VRAM for a few minutes, which would starve the next torch job.
    req = urllib.request.Request(f"{OLLAMA}/api/generate", method="POST",
                                 data=json.dumps({"model": "qwen2.5:7b", "keep_alive": 0}).encode())
    try:
        urllib.request.urlopen(req, timeout=60).read()
    except OSError:
        pass


def check_ollama() -> None:
    try:
        urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=10).read()
    except OSError as e:
        raise RuntimeError(f"Ollama is not reachable at {OLLAMA} ({e})") from e


def validate(name: str, min_free_gb: float, params: list[str] = ()) -> None:
    """A validation run (resumes from partial.jsonl), then re-scoring under rule 2."""
    args = [name, "--min-free-gb", str(min_free_gb)]
    for p in params:
        args += ["--param", p]
    # If only the re-scoring failed last time, the run itself doesn't need repeating.
    if not (RESULTS / f"{name}.json").exists():
        run(python("run_experiment.py", *args), RUNS / name / "log.txt")
    run(python("rescore.py", name), RUNS / name / "log.txt")


def train(name: str) -> None:
    """Trains the model for one experiment entry; rerunning resumes from its checkpoint."""
    cfg = {e["name"]: e for e in yaml.safe_load(CONFIG.read_text())["experiments"]}[name]
    out = cfg["params"]["model_dir"]
    run(python("train_qa.py", *cfg["train"].split(), "--out", out),
        RUNS / name / "train_log.txt")


def timing_done() -> bool:
    log_path = RUNS / "timing-deberta-v3-base" / "log.txt"
    return log_path.exists() and "per optimiser step" in log_path.read_text(encoding="utf-8")


def timing() -> None:
    out = RUNS / "timing-deberta-v3-base" / "log.txt"
    try:
        run(python("train_qa.py", "--model", "microsoft/deberta-v3-base", "--time-only"), out)
    except RuntimeError as e:
        # The base model may not fit in 6 GB of VRAM as is, so I retry with gradient
        # checkpointing, which trades speed for memory.
        log(f"  timing without gradient checkpointing failed ({e}); retrying with it")
        run(python("train_qa.py", "--model", "microsoft/deberta-v3-base", "--time-only",
                   "--grad-checkpointing"), out)


def jobs(min_free_gb: float) -> list[tuple[str, Callable[[], bool], Callable[[], None]]]:
    """(name, already finished?, run it) for every job, in queue order."""
    def done(name: str) -> Callable[[], bool]:
        return lambda: rescored(name)

    def hybrid(name: str) -> Callable[[], None]:
        def run_it() -> None:
            check_ollama()
            source = better_qa()
            try:
                validate(name, min_free_gb, [f"candidates=runs/{source}/findings.jsonl"])
            finally:
                unload_ollama()
        return run_it

    def llm(name: str) -> Callable[[], None]:
        def run_it() -> None:
            check_ollama()
            try:
                validate(name, min_free_gb)
            finally:
                unload_ollama()
        return run_it

    def second_seed_name(quiet: bool = True) -> str:
        return better_qa(quiet).replace("-s0", "-s1")

    def second_seed() -> None:
        name = second_seed_name(quiet=False)
        model_dir = ROOT / "models" / name
        if not (model_dir / "train_info.json").exists():
            log(f"  training {name}")
            train(name)
        log(f"  validating {name}")
        validate(name, min_free_gb)

    return [
        ("qa-small-e4-s0 validation", done("qa-small-e4-s0"),
         lambda: validate("qa-small-e4-s0", min_free_gb)),
        # llm-qwen7b-v1 is left out: it times out on the same contract every time, so it stays
        # in the report as an incomplete run and v2 (with an answer cap) replaces it below.
        ("hybrid-qwen7b-v1 validation", done("hybrid-qwen7b-v1"), hybrid("hybrid-qwen7b-v1")),
        ("deberta-v3-base timing", timing_done, timing),
        ("second QA seed", lambda: rescored(second_seed_name()), second_seed),
        ("llm-qwen7b-v2 validation", done("llm-qwen7b-v2"), llm("llm-qwen7b-v2")),
        ("hybrid-qwen7b-v2 validation", done("hybrid-qwen7b-v2"), hybrid("hybrid-qwen7b-v2")),
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="only say what would run")
    ap.add_argument("--min-free-gb", type=float, default=1.5,
                    help="wait before each job, and each contract, while less RAM is free")
    args = ap.parse_args()

    if not args.dry_run:
        log("Queue started")
    for name, finished, start in jobs(args.min_free_gb):
        try:
            is_done = finished()
        except RuntimeError as e:
            is_done = False
            print(f"{name}: can't tell yet ({e})")
        if args.dry_run:
            print(f"{name}: {'finished, skip' if is_done else 'would run'}")
            continue
        if is_done:
            log(f"SKIP {name} (already finished)")
            continue
        # Same RAM check as the runs themselves, before a job loads anything.
        waited = wait_for_memory(args.min_free_gb, log=log)
        if waited:
            log(f"  waited {waited / 60:.0f} min for free RAM")
        log(f"START {name}")
        try:
            start()
        except KeyboardInterrupt:
            # Ctrl+C reaches the job and the queue together, so I log it and stop the queue.
            log(f"STOPPED {name} (interrupted; rerun the queue to resume)")
            raise SystemExit(1) from None
        except Exception as e:  # noqa: BLE001
            # One failed job shouldn't hold up the rest of the queue.
            log(f"FAILED {name}: {e}")
            continue
        log(f"FINISHED {name}")
    if not args.dry_run:
        log("Queue finished")


if __name__ == "__main__":
    main()
