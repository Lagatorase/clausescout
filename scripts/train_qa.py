"""Fine-tune an extractive QA model on CUAD's training contracts (my train split only).

Mixed precision uses bf16, because DeBERTa-v3 overflows in fp16. A checkpoint is saved every
--save-every optimiser steps, and rerunning the same command resumes from it. With --time-only
the script runs a short warm-up and a timed stretch, then prints an estimate of the full run
without saving anything.

Usage:
  python scripts/train_qa.py --model microsoft/deberta-v3-small --out models/qa-small-s0
  python scripts/train_qa.py --model microsoft/deberta-v3-small --time-only
"""

import argparse
import json
import random
import time
from functools import partial
from pathlib import Path

import numpy as np
import torch
from transformers import (
    AutoModelForQuestionAnswering,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)

from clausescout.data.cuad import load_split
from clausescout.models.qa import (
    FeatureDataset,
    Windows,
    collate,
    cuad_questions,
    training_features,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="microsoft/deberta-v3-small")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--lr", type=float, default=3e-5)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--accum", type=int, default=8)
    ap.add_argument("--neg-ratio", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--save-every", type=int, default=200)
    ap.add_argument("--time-only", action="store_true")
    ap.add_argument("--grad-checkpointing", action="store_true")
    args = ap.parse_args()
    if not args.time_only and args.out is None:
        ap.error("--out is needed unless --time-only")

    # I fix every seed so a rerun (or a resume) sees the same data order.
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    t0 = time.perf_counter()
    tok = AutoTokenizer.from_pretrained(args.model)
    questions = cuad_questions()
    windows = Windows(tok, questions)
    encoded, rows, counts = training_features(windows, load_split("train"), seed=args.seed,
                                              neg_ratio=args.neg_ratio)
    print(f"Features: {counts['positives']} positive, {counts['negatives']} negative "
          f"({time.perf_counter() - t0:.0f}s to build)")
    data = FeatureDataset(windows, encoded, rows)
    loader = torch.utils.data.DataLoader(
        data, batch_size=args.batch, shuffle=False,
        collate_fn=partial(collate, pad_id=tok.pad_token_id),
    )

    device = "cuda"
    # transformers 5 loads weights in the dtype they were saved in, which is fp16 for DeBERTa-v3.
    # AdamW on fp16 weights turns them into NaN after one step, so I load fp32 master weights
    # and use bf16 only for the forward and backward passes through autocast.
    model = AutoModelForQuestionAnswering.from_pretrained(args.model, dtype=torch.float32)
    model = model.to(device)
    if args.grad_checkpointing:
        model.gradient_checkpointing_enable()
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    steps_per_epoch = len(loader) // args.accum
    total = steps_per_epoch * args.epochs
    sched = get_linear_schedule_with_warmup(opt, int(0.1 * total), total)

    # Resume from the last checkpoint if there is one.
    step, ckpt = 0, (args.out / "checkpoint.pt") if args.out else None
    if ckpt and ckpt.exists():
        state = torch.load(ckpt, map_location=device, weights_only=False)
        model.load_state_dict(state["model"])
        opt.load_state_dict(state["opt"])
        sched.load_state_dict(state["sched"])
        step = state["step"]
        print(f"Resumed at step {step}/{total}")

    model.train()
    timed_from, timed_steps = None, 0
    started = time.perf_counter()
    for epoch in range(step // steps_per_epoch, args.epochs):
        # Each epoch gets its own fixed shuffle, so resuming lands on the same batches.
        order = list(range(len(rows)))
        random.Random(args.seed * 1000 + epoch).shuffle(order)
        data.rows = [rows[i] for i in order]
        skip = (step % steps_per_epoch) * args.accum
        for k, batch in enumerate(loader):
            if k < skip:
                continue
            batch = {key: v.to(device) for key, v in batch.items()}
            with torch.autocast("cuda", dtype=torch.bfloat16):
                loss = model(**batch).loss / args.accum
            loss.backward()
            if (k + 1) % args.accum:
                continue
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            opt.zero_grad(set_to_none=True)
            step += 1

            if args.time_only:
                # The first 10 steps warm up the GPU, then I time the next 40.
                if step == 10:
                    torch.cuda.synchronize()
                    timed_from = time.perf_counter()
                elif step > 10:
                    timed_steps += 1
                if timed_steps == 40:
                    torch.cuda.synchronize()
                    per_step = (time.perf_counter() - timed_from) / timed_steps
                    mem = torch.cuda.max_memory_allocated() / 2**30
                    print(f"{per_step:.3f}s per optimiser step ({args.batch}x{args.accum} "
                          f"windows), peak GPU memory {mem:.2f} GB")
                    print(f"{total} steps for {args.epochs} epoch(s): about "
                          f"{per_step * total / 3600:.2f} hours")
                    return
                continue

            if step % 50 == 0:
                rate = (time.perf_counter() - started) / max(step, 1)
                print(f"step {step}/{total} loss {loss.item() * args.accum:.3f} "
                      f"({rate * (total - step) / 60:.0f} min left)", flush=True)
            if step % args.save_every == 0 or step == total:
                args.out.mkdir(parents=True, exist_ok=True)
                torch.save({"model": model.state_dict(), "opt": opt.state_dict(),
                            "sched": sched.state_dict(), "step": step}, ckpt)

    # Save the final model in the usual Hugging Face layout, with the questions it was trained on.
    model.save_pretrained(args.out)
    tok.save_pretrained(args.out)
    (args.out / "questions.json").write_text(json.dumps(questions, indent=1), encoding="utf-8")
    info = {**vars(args), "out": str(args.out), "features": counts, "steps": total,
            "train_hours": (time.perf_counter() - t0) / 3600}
    (args.out / "train_info.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    ckpt.unlink(missing_ok=True)
    print(f"Saved {args.out}")


if __name__ == "__main__":
    main()
