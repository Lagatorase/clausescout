# Model card: ClauseScout QA (DeBERTa-v3-small, CUAD)

## What it is

An extractive question-answering model that finds contract clauses. For each of the 41 CUAD
clause types it is asked a question (CUAD's own question for that type) and returns spans of the
contract, each with a probability that the span answers it rather than "no answer".

- Base model: `microsoft/deberta-v3-small` (MIT license).
- Fine-tuned on: CUAD v1 (CC BY 4.0), 346 training contracts only.
- Code: `scripts/train_qa.py`, `clausescout/models/qa.py`.
- Weights are not published.

## Intended use

A first pass over commercial contracts in due diligence, inside ClauseScout, where every
predicted span is checked word for word against the contract and shown to a reviewer with its
location. It is a review aid, not legal advice, and is not meant to decide anything on its own.

Out of scope: deciding that a clause is absent, contracts that are not in English, scanned
documents without OCR, and legal interpretation of what a clause means.

## Training

| Setting | Value |
|---|---|
| Training contracts | 346 (CUAD train, split by contract; 62 more held out for validation) |
| Windows | 512 tokens, stride 256, question truncated to 64 tokens |
| Features | 12,980 with an answer, 12,989 without (one negative per positive, sampled) |
| Epochs | 1 (811 optimiser steps) |
| Batch | 4 windows, 8 accumulation steps (effective 32) |
| Learning rate | 3e-5 |
| Precision | bf16 autocast with fp32 master weights |
| Seed | 0 |
| Hardware | RTX 4050 laptop GPU (6 GB), Windows 11 |
| Training time | 18 minutes |

The CUAD paper trained larger models for longer. This one is small so it trains on a laptop.

## Evaluation

Validation (62 contracts, used for every decision):

| Metric | Value |
|---|---:|
| Span AUPR | 0.288 (0.259-0.314) |
| Precision at 80% recall | 0.171 (0.102-0.211) |
| Precision at 90% recall | 0.000 (0.000-0.055) |
| Inference time | 49 s per contract on the laptop GPU |

Test results (CUAD's 102 test contracts, run once) are added here after the final comparison.

## Known weaknesses

- Its presence score barely separates contracts that have a clause from those that don't:
  high-stakes precision stays between 0.44 and 0.53 at every threshold on validation. Training
  with one sampled negative per positive likely makes it too willing to answer.
- At low thresholds it finds a correct quote for most present clauses, but returns about 113
  findings per contract, which is too many for a reviewer to read. It is more useful as a
  candidate generator (the hybrid method) than on its own.
- Trained only on US public-company filings; drafting styles elsewhere (for example Singapore)
  are untested until the Singapore set is labelled.
