---
license: cc-by-4.0
language: en
library_name: transformers
pipeline_tag: question-answering
base_model: microsoft/deberta-v3-small
datasets:
  - theatticusproject/cuad
tags:
  - legal
  - contracts
  - cuad
  - extractive-qa
  - deberta-v3
---

# ClauseScout QA: DeBERTa-v3-small fine-tuned on CUAD

An extractive question-answering model that finds clauses in commercial contracts. For each of
the 41 CUAD clause types I ask it CUAD's own question for that type, and it returns spans of the
contract, each with a score for how likely the span answers the question rather than "no
answer". I trained it for ClauseScout, a local-first contract review project
([GitHub](https://github.com/Lagatorase/clausescout)), where it is the app's default method.

**This model is a review aid, not legal advice.** It misses clauses and mislabels some. Every
span it returns should be read in the contract by a person, and "no answer" never means a clause
is absent.

## Intended use

A first pass over English-language commercial contracts, for example in due diligence: it points
a reviewer at the passages most likely to be a governing law clause, a change of control clause,
a cap on liability and so on. In ClauseScout every span is checked word for word against the
contract and shown with its page or paragraph, and at most 2 spans per clause type are shown.

Out of scope: deciding on its own that a clause is present or absent, legal interpretation of
what a clause means, contracts that are not in English, and scanned documents without OCR.

## Base model and data

- Base model: [`microsoft/deberta-v3-small`](https://huggingface.co/microsoft/deberta-v3-small)
  (MIT licence).
- Training data: CUAD v1, the Contract Understanding Atticus Dataset (CC BY 4.0), 510 contracts
  from US SEC EDGAR filings, labelled by lawyers for 41 clause types.
- Split by contract, so no contract is in more than one part: CUAD's training contracts are split
  into 346 for training and 62 for validation, and CUAD's 102 test contracts are kept for the
  end. The model was trained on the 346 training contracts only. Every decision (epochs,
  threshold, which method the app uses) was made on the 62 validation contracts, and the test
  contracts were run once, at the end.

## Training

| Setting | Value |
|---|---|
| Training contracts | 346 |
| Windows | 512 tokens, stride 256, question truncated to 64 tokens |
| Features | 12,980 with an answer, 12,989 without (one sampled negative per positive) |
| Epochs | 4 (3,244 optimiser steps) |
| Batch | 4 windows, 8 accumulation steps (effective 32) |
| Learning rate | 3e-5 |
| Precision | bf16 autocast with fp32 master weights (DeBERTa-v3 overflows in fp16) |
| Seed | 0 |
| Hardware | RTX 4050 laptop GPU (6 GB), Windows 11 |

I picked the small model so it trains and runs on a laptop. The CUAD paper trained larger models.

## Results

How I score it: each contract gets at most 2 spans per clause type, at the threshold chosen on
validation (0.1). A clause type only counts as found if one of those spans is a correct quote.
The main measure is high-stakes found F2: F2 (recall weighted twice as much as precision) over 8
clause types where a miss is costly (Anti-Assignment, Cap On Liability, Change Of Control,
Exclusivity, Governing Law, Non-Compete, Termination For Convenience, Uncapped Liability).
Intervals are 95% bootstrap intervals over contracts.

| Measure | Validation (62 contracts) | Test (102 contracts, run once) |
|---|---:|---:|
| High-stakes found F2 | 0.763 (0.696-0.820) | 0.752 (0.708-0.787) |
| High-stakes found recall | 0.893 | 0.916 |
| Span AUPR (CUAD's span measure, all 41 types) | 0.391 (0.358-0.424) | 0.378 (0.356-0.405) |
| Precision at 80% recall | 0.318 (0.269-0.355) | 0.324 (0.278-0.356) |
| Spans shown per contract | 41.8 | 35.8 |
| Seconds per contract (laptop GPU) | 52.4 | 48.2 |

For comparison, on the same test contracts:

- A keyword baseline scored 0.500 (0.432-0.568) high-stakes found F2.
- A hybrid where a local LLM (qwen2.5:7b) checks this model's candidates scored 0.745
  (0.698-0.782), level with this model on its own and about 1.6 times slower.
- On validation, a general-purpose local LLM (qwen2.5:7b, no fine-tuning) scored 0.381
  (0.315-0.440), about 0.38 below this model.
- A second training seed scored 0.771 on validation against 0.763 for this one, so training noise
  is small next to the noise from having only 62 validation contracts.

## Grounding check

ClauseScout keeps a span only if it appears in the contract word for word (allowing only
typographic differences such as curly quotes and whitespace). An extractive model can only point
at text that is there, and none of this model's spans failed the check: 0 of 50,840 rejected on
validation and 0 of 83,620 on test. For the local LLM on its own, the same check rejected 36.7%
of its quotes on validation.

## Limitations

- Trained and tested only on CUAD, which is US public-company filings from SEC EDGAR. Drafting
  styles from other places are untested. A set of 15 Singapore contracts is being labelled, and
  there are no Singapore results yet.
- It finds a correct quote for most present high-stakes clauses, but it also answers for many
  that aren't there: on test, only 53% of the high-stakes clause types it says are present
  really are (58% on validation). With about 36 to 42 spans per contract, a reviewer still has a
  fair amount to read.
- Validation scores are slightly optimistic, because the threshold was tuned on the same 62
  contracts. The test numbers are the fair ones.

## Usage

`questions.json` holds CUAD's question for each clause type. This finds the best span for a few
clause types in a short text (transformers 5 removed the question-answering pipeline, so it uses
the model directly):

```python
import json

import torch
from huggingface_hub import hf_hub_download
from transformers import AutoModelForQuestionAnswering, AutoTokenizer

repo = "Lagatorase/clausescout-deberta-v3-small-cuad"
tok = AutoTokenizer.from_pretrained(repo)
model = AutoModelForQuestionAnswering.from_pretrained(repo).eval()
questions = json.load(open(hf_hub_download(repo, "questions.json"), encoding="utf-8"))

contract = ("This Agreement shall be governed by the laws of the State of New York. "
            "Neither party may assign this Agreement without the prior written consent of the "
            "other party.")
for clause in ["Governing Law", "Anti-Assignment", "Non-Compete"]:
    enc = tok(questions[clause], contract, return_tensors="pt", truncation="only_second",
              max_length=512, return_offsets_mapping=True)
    offsets = enc.pop("offset_mapping")[0]
    with torch.no_grad():
        out = model(**enc)
    start, end = out.start_logits[0], out.end_logits[0]
    # Only spans inside the contract count; position 0 ([CLS]) means "no answer".
    in_context = torch.tensor([i == 1 for i in enc.sequence_ids(0)])
    s = int(torch.where(in_context, start, -1e9).argmax())
    e = s + int(torch.where(in_context, end, -1e9)[s:s + 200].argmax())
    if float(start[s] + end[e]) > float(start[0] + end[0]):
        print(f"{clause}: {contract[offsets[s][0]:offsets[e][1]]!r}")
    else:
        print(f"{clause}: no answer")
```

This prints the governing law sentence, the assignment sentence and "no answer" for
Non-Compete. For whole contracts (windows, scores across the 41 types, the grounding check and
page locations), use `clausescout/models/qa.py` in the GitHub repo.

## Licence and credits

The fine-tuned weights are released under CC BY 4.0, following the training data. The base
model, `microsoft/deberta-v3-small`, is under the MIT licence.

CUAD is by Dan Hendrycks, Collin Burns, Anya Chen and Spencer Ball, from The Atticus Project, and
is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

```bibtex
@article{hendrycks2021cuad,
  title={CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review},
  author={Dan Hendrycks and Collin Burns and Anya Chen and Spencer Ball},
  journal={NeurIPS},
  year={2021}
}
```
