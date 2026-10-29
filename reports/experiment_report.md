# Experiment report (validation)

All numbers in this report come from the 62 validation contracts. CUAD's 102 test contracts
are untouched until the final configuration has been chosen.

## How the final configuration is chosen

### The rule in use (rule 2)

1. Every method shows at most 2 quotes per clause type per contract: its top 2 by score.
2. Each method's threshold is chosen on validation to maximise mean high-stakes found F2 over
   the eight high-stakes clause types (Cap On Liability, Uncapped Liability, Termination For
   Convenience, Change Of Control, Anti-Assignment, Exclusivity, Non-Compete, Governing Law).
   Found F2 only counts a "yes" as a hit when it comes with a correct quote; a "yes" without
   one counts both as a miss and as a false alarm. F2 counts recall twice as much as precision,
   because a missed clause costs more in due diligence than an extra one to read.
3. The final configuration is the method with the highest high-stakes found F2 on validation.
   If the top methods' 95% bootstrap intervals overlap, I prefer the one that runs fully
   locally, then the one with fewer findings per contract, then the faster one.
4. Findings per contract (after the cap and the threshold) is reported for every method, as a
   measure of how much a reviewer has to read.

Span-level metrics (AUPR, precision at 80% and 90% recall) still use every finding a method
returns, uncapped, so they stay comparable with the CUAD paper.

### Why the rule was changed

Rule 2 replaced the original rule after I had seen validation results. No test data was used
for either rule or for the change. The original rule (written down before comparing methods)
was:

> The final configuration is the method with the highest mean contract-level F2 over the eight
> high-stakes clause types on validation. If the top methods are within run-to-run noise, or
> their 95% bootstrap intervals overlap, prefer the one that runs fully locally, then the
> cheaper one, then the faster one.

It was won by saying yes. About half of the high-stakes (contract, clause type) pairs have the
clause, and at that base rate F2 rewards predicting "present" everywhere: a reference row that
says every clause is present and quotes nothing scored 0.789, and the threshold sweep pushed the
fine-tuned QA model down to 0.05, where it returned about 113 findings per contract. Found F2
can't be won without correct quotes, and the cap of 2 stops a method from winning by quoting
everything.

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
`scripts/rescore.py` under rule 2, the same way for every method (highest mean high-stakes found
F2 on validation, top 2 quotes per type), so validation scores are slightly optimistic for all
of them. Span AUPR uses every finding, uncapped.

| Method | Threshold | Span AUPR | High-stakes found F2 | Findings per contract | Seconds per contract |
|---|---:|---:|---:|---:|---:|
| always-present | n/a | 0.000 | 0.000 | 41.0 | 0 |
| keywords-v1 | 0.5 | 0.334 (0.298-0.371) | 0.445 (0.384-0.504) | 19.1 | 0.1 |
| qa-small-e1-s0 | 0.05 | 0.288 (0.259-0.314) | 0.703 (0.636-0.759) | 61.2 | 48.9 |
| qa-small-e4-s0 | 0.1 | 0.391 (0.358-0.424) | 0.763 (0.696-0.820) | 41.8 | 52.4 |

What these show so far:

- **Four epochs help QA on every measure, but the gain is within the noise.** Against one
  epoch, high-stakes found F2 rises from 0.703 to 0.763 with overlapping intervals, span AUPR
  from 0.288 to 0.391 (now above keywords' 0.334), and findings per contract fall from 61.2 to
  41.8 because the chosen threshold rises from 0.05 to 0.1. Only one seed has been run so far.
- **QA (1 epoch) leads on the selection metric.** Its high-stakes found F2 of 0.703 is above
  keywords' 0.445, and the intervals don't overlap. Always-present scores 0, as intended: it
  quotes nothing.
- **QA still prefers the lowest threshold.** Even with the top 2 cap, dropping its low-score
  quotes loses more correct quotes than it saves false alarms. At 0.05 it shows 61 findings per
  contract, about three times what keywords show.
- **Keywords beat QA on span AUPR** (0.334 against 0.288), but QA ranks better at high recall
  (precision at 80% recall 0.171 against 0). Keywords never reach 80% recall at any threshold.
- **QA's presence score is weak, its candidate list is strong.** High-stakes precision stays
  between 0.44 and 0.53 whatever the threshold, so the score barely separates real clauses from
  absent ones. That is what the hybrid method builds on: the local LLM confirms or rejects QA's
  candidates.

## Notes

- Price Restrictions has no test contracts (13 train, 2 validation, 0 test), so it has no test
  score; the CUAD paper notes the same. It is still trained on and scored on validation.
- Run-to-run noise: a second QA seed has not been run yet. Until it is, the only noise
  estimate is the bootstrap interval over contracts, which does not cover training variation.
