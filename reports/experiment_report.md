# Experiment report (validation)

All numbers in this report come from the 62 validation contracts. CUAD's 102 test contracts
are untouched until the final configuration has been chosen.

## How the final configuration is chosen

I wrote this rule down before comparing any method other than the keyword baseline, so the
choice can't drift towards whichever result looks best afterwards.

1. The final configuration is the method with the highest mean contract-level F2 over the eight
   high-stakes clause types (Cap On Liability, Uncapped Liability, Termination For Convenience,
   Change Of Control, Anti-Assignment, Exclusivity, Non-Compete, Governing Law) on validation.
   F2 counts recall twice as much as precision, because a missed clause in due diligence costs
   more than an extra clause to read.
2. If the top methods are within run-to-run noise, or their 95% bootstrap intervals overlap, I
   prefer the one that runs fully locally, then the cheaper one, then the faster one.

Method 5 (a hosted LLM through the Anthropic API) is not yet run. It costs money, so I left it
out, and it is not part of this choice.

## Methods

Every method returns quotes with a score in [0, 1]. Every quote then goes through the same
grounding check (it must be in the contract word for word, allowing only typographic
differences), and the metrics only see what survives.

| Name | Method | Notes |
|---|---|---|
| always-present | Says every clause type is present, quotes nothing | A reference row, not a method. It shows how much of a contract-level score comes from saying yes. |
| keywords-v1 | Hand-written regular expressions per clause type | Sentence-level matches; titles and dates matched directly. CPU only. |
| qa-small-e1-s0 | Fine-tuned extractive QA, DeBERTa-v3-small | CUAD's own questions, 1 epoch, seed 0, trained on the 346 training contracts. |
| llm-qwen7b-v1 | Local LLM, qwen2.5:7b (Q4) via Ollama | 12,000-character chunks with 1,500 overlap, strict JSON schema, temperature 0, prompt v1. |
| hybrid | The local LLM confirms and classifies QA candidates | Uses the QA run's findings as candidates. |
| hosted LLM | Anthropic API | Not yet run: it costs money. |

## Results so far

The full tables are in `reports/validation_tables.md`, generated from
`experiments/results/`. Each method's contract-level threshold was picked by
`scripts/rescore.py`, the same way for every method (highest mean high-stakes F2 on validation),
so validation scores are slightly optimistic for all of them.

| Method | Span AUPR | High-stakes F2 | High-stakes found F2 | Seconds per contract |
|---|---:|---:|---:|---:|
| always-present | 0.000 | 0.789 (0.735-0.829) | 0.000 | 0 |
| keywords-v1 | 0.334 (0.298-0.371) | 0.688 (0.632-0.735) | 0.517 (0.451-0.578) | 0.1 |
| qa-small-e1-s0 (threshold 0.05) | 0.288 (0.259-0.314) | 0.805 (0.752-0.841) | 0.762 (0.704-0.807) | 48.9 |

What these show so far:

- **The rule as written can be won by saying yes.** About half of the high-stakes (contract,
  clause type) pairs have the clause, and at that base rate F2 rewards predicting "present"
  everywhere: always-present scores 0.789 without quoting anything. The threshold sweep pushed
  QA to 0.05, where it predicts nearly every clause type in every contract. QA is level with
  always-present on high-stakes F2 (overlapping intervals), so on this metric the fine-tuned
  model shows no measurable gain over saying yes. I have not changed the rule; the choice is
  left as an open question.
- **Keywords beat QA on span AUPR** (0.334 against 0.288), but QA ranks better at high recall
  (precision at 80% recall 0.171 against 0). Keywords never reach 80% recall at any threshold.
- **QA's presence score is weak, its candidate list is strong.** High-stakes precision stays
  between 0.44 and 0.53 whatever the threshold, so the score barely separates real clauses from
  absent ones. But at 0.05 it quotes a correct span for 94% of present high-stakes clauses,
  which is what the hybrid method builds on.

## Notes

- Price Restrictions has no test contracts (13 train, 2 validation, 0 test), so it has no test
  score; the CUAD paper notes the same. It is still trained on and scored on validation.
- Run-to-run noise: a second QA seed has not been run yet. Until it is, the only noise
  estimate is the bootstrap interval over contracts, which does not cover training variation.
