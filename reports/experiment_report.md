# Experiment report

Everything up to "Test results" comes from the 62 validation contracts. The final configuration
was chosen on validation only, before any test contract was run. CUAD's 102 test contracts are
then used once, for the final comparison.

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
| qa-small-e4-s0, qa-small-e4-s1 | The same, 4 epochs | Seeds 0 and 1. Seed 1 measures training noise. |
| llm-qwen7b-v1 | Local LLM, qwen2.5:7b (Q4) via Ollama | 12,000-character chunks with 1,500 overlap, strict JSON schema, temperature 0, prompt v1. Incomplete: 23 of 62 contracts. |
| llm-qwen7b-v2 | v1 plus a per-request answer cap | The only change from v1; see "Local LLM" below. |
| hybrid-qwen7b-v1, -v2 | The local LLM confirms and classifies QA candidates | Candidates from qa-small-e4-s0 (QA probability at least 0.05), 8 passages per request. v2 adds the answer cap. |
| hosted LLM | Anthropic API | Not run: it costs money. |

## Validation results

The full tables are in `reports/validation_tables.md`, generated from `experiments/results/`.
Each method's contract-level threshold was picked by `scripts/rescore.py` under rule 2, the same
way for every method (highest mean high-stakes found F2 on validation, top 2 quotes per type),
so validation scores are slightly optimistic for all of them. Span AUPR uses every finding,
uncapped. Intervals are 95% bootstrap intervals over contracts.

| Method | Threshold | Span AUPR | High-stakes found F2 | Findings per contract | Seconds per contract |
|---|---:|---:|---:|---:|---:|
| always-present | n/a | 0.000 | 0.000 | 41.0 | 0 |
| keywords-v1 | 0.5 | 0.334 (0.298-0.371) | 0.445 (0.384-0.504) | 19.1 | 0.1 |
| qa-small-e1-s0 | 0.05 | 0.288 (0.259-0.314) | 0.703 (0.636-0.759) | 61.2 | 48.9 |
| qa-small-e4-s0 | 0.1 | 0.391 (0.358-0.424) | 0.763 (0.696-0.820) | 41.8 | 52.4 |
| qa-small-e4-s1 (second seed) | 0.05 | 0.399 (0.369-0.432) | 0.771 (0.712-0.819) | 44.5 | 48.9 |
| llm-qwen7b-v2 | 0.9 | 0.168 (0.144-0.196) | 0.381 (0.315-0.440) | 12.9 | 153.7 |
| hybrid-qwen7b-v1 | 0.15 | 0.451 (0.404-0.492) | 0.780 (0.717-0.833) | 39.9 | 87.5 |
| hybrid-qwen7b-v2 | 0.15 | 0.451 (0.404-0.492) | 0.780 (0.717-0.833) | 39.9 | 86.3 |

What these show:

- **Fine-tuning beats the general-purpose local LLM by a wide margin.** QA (4 epochs, seed 0)
  scores 0.763 against the local LLM's 0.381, a gap of about 0.38, with intervals far apart.
  The LLM's quotes are often not word for word: the grounding check rejected 775 of its 2,114
  quotes (36.7%), against 0 of 50,840 for the same QA model (5 of 50,840 for 1 epoch).
- **Four epochs help QA on every measure, but the gain is within the noise.** Against one
  epoch, high-stakes found F2 rises from 0.703 to 0.763 with overlapping intervals, span AUPR
  from 0.288 to 0.391 (above keywords' 0.334), and findings per contract fall from 61.2 to 41.8.
- **Training noise is small next to contract noise.** The second seed scores 0.771 against
  0.763, a difference of about 0.01, while each interval is about 0.11 wide. Two seeds is a thin
  basis, but it suggests most of the uncertainty comes from having only 62 validation contracts.
- **The hybrid adds little on top of QA.** It scores 0.780 against QA's 0.763, shows 39.9
  findings per contract against 41.8, and has the best span AUPR (0.451). But it never reaches
  80% recall (precision at 80% recall 0, QA 0.318), because the passages the LLM rejects drop
  far down the ranking. It takes 86 s per contract against QA's 52 s.
- **QA's presence score is weak, its candidate list is strong.** High-stakes precision stays
  between 0.44 and 0.59 for every QA run, whatever the threshold, so the score barely separates real clauses from absent
  ones, and the threshold sweep keeps choosing low thresholds (0.05 to 0.1).
- **Keywords are precise but miss a lot.** They show 19.1 findings per contract but find a
  correct quote far less often (0.445).

## The selection (rule 2)

Applied on validation, before any test contract was run.

1. **Highest high-stakes found F2:** hybrid-qwen7b-v2, 0.780 (0.717-0.833). hybrid-qwen7b-v1
   is identical (same findings and scores), so I use v2, which has the answer cap.
2. **Do the top intervals overlap?** Yes. The hybrid's interval overlaps QA 4 epochs seed 1
   (0.712-0.819), QA 4 epochs seed 0 (0.696-0.820) and QA 1 epoch (0.636-0.759). Keywords
   (0.384-0.504) and the local LLM (0.315-0.440) are clearly below and drop out.
3. **First tie-break, runs fully locally:** all four do, so this doesn't separate them.
4. **Second tie-break, fewer findings per contract:** hybrid 39.9, QA 4 epochs seed 0 41.8,
   seed 1 44.5, QA 1 epoch 61.2. The hybrid has the fewest.
5. **The choice:** hybrid-qwen7b-v2, the qwen2.5:7b local LLM checking candidates from QA
   (DeBERTa-v3-small, 4 epochs, seed 0), at threshold 0.15.

Said plainly: the selected method is within error of a simpler and faster one. QA alone
(4 epochs) scores 0.763 against the hybrid's 0.780 with overlapping intervals, is about 1.6
times faster (52 s against 86 s per contract on this laptop) and needs no LLM. The hybrid wins
only on the second tie-break, by about 2 findings per contract. The test run reports both, so
the comparison can be checked on contracts neither was tuned on.

## Local LLM: an incomplete run and an answer cap

### llm-qwen7b-v1 did not finish

The first local LLM run (qwen2.5:7b through Ollama, no limit on answer length) finished 23 of
the 62 validation contracts and then failed twice on contract 24, once with 1 GB of RAM free
and once with about 5 GB free. Each time, one request ran until it hit the client's 600 s
timeout, three tries in a row, and the run stopped. Decoding is set to temperature 0 with a
fixed seed, and the same request failed in both runs, so retrying didn't help. (Later runs
showed Ollama isn't fully reproducible even so; see "Checking v2 against v1".) My
reading, which the logs support but do not prove, is that the model started an answer it never
closed: with the context window full, Ollama keeps generating until something stops it.

This is a finding about running local LLMs unattended, not only a bug in my run. A hosted API
returns an error or a cut answer within a bounded time; a local server will happily spend hours
on one request. Without a cap on answer length, a single chunk can stall an overnight run, and a
retry policy makes it worse rather than better. v1 stays in this report as an incomplete run
(23 of 62 contracts) and is not part of the selection.

### Answer cap (llm-qwen7b-v2)

v2 is v1 with one change: a cap on each answer's length (Ollama's `num_predict`), plus a longer
request timeout so the cap, not the timeout, ends a runaway answer. The prompt, chunking (12,000
characters, 1,500 overlap), context window (6,144 tokens), temperature and seed are the same.

The prompt and the answer share the 6,144-token window, so an answer that ends by itself can't be
longer than the window minus its prompt. A fixed cap doesn't fit that: prompts vary, and Ollama
doesn't stop when the window is full but shifts the context and carries on. So each request's cap
is set from its own prompt:

- cap = 6,144 minus the prompt's tokens minus a margin of 16 tokens, and at least 64.
- Ollama can't count a prompt's tokens before the request, so I count them with the model's own
  tokenizer and chat template (Qwen2.5). On v1's 154 requests this matched Ollama's own prompt
  count (`prompt_eval_count`) exactly, to the token, for all 23 contracts.
- v1's prompts ran from 1,841 to 5,069 tokens, so caps run from about 4,287 down to about 1,059
  tokens.
- Any answer that fits in the window is never cut, except one that comes within 16 tokens of
  filling it. An answer that would have overflowed the window stops when the window is full.
- The request timeout goes from 600 s to 900 s. A full window of answer is at most about 4,300
  tokens, about 5 minutes at the roughly 14 tokens per second v1 managed, so the cap always ends
  a runaway answer before the timeout.

What v1 tells me about answer lengths (it kept token counts per contract, not per request):

- 154 requests and 56,165 output tokens, 365 per request on average. The mean per request in a
  contract ranges from 31 to 1,022 (median 458). The longest answer is at least 1,023 tokens
  (one contract had 2 requests and 2,045 output tokens).
- One v1 request filled the window. Under v2's cap it would be cut, so v2 should differ from v1
  on that contract. Any other v1 request that came within 16 tokens of filling the window would
  be cut too; I can't tell from v1's totals whether there were any.
- v2 logs every request (`runs/llm-qwen7b-v2/requests.jsonl`): prompt tokens (Ollama's count and
  mine), output tokens, the cap applied and whether it was hit. The longest answer that ended by
  itself, and how far it was below its cap, will come from that log.

A request that stops at the cap is counted, and its log line says which contract and chunk it
came from. Its complete findings are kept (the JSON is parsed up to the last whole item), and
the log says whether a half-written item was lost. It is not scored as "nothing found".

The hybrid used the same uncapped client. It finished without a timeout, but it could have hit
the same problem, so it is rerun as hybrid-qwen7b-v2 with the same per-request cap and timeout,
on the same candidates.

### Checking v2 against v1

Before v2 ran, I set what counts as the same result on the 23 contracts v1 finished: at least
95% of findings (same contract, type and quote) in both runs, and a difference in high-stakes
found F2 of at most 0.02 at the same threshold. The comparison is written by
`scripts/compare_llm_runs.py` (`reports/compare_llm-qwen7b-v1_llm-qwen7b-v2.md`).

What happened:

- 87.2% of findings match (761 in both, 24 only in v1, 88 only in v2), below the 95% limit.
- High-stakes found F2 is 0.403 for v1 and 0.389 for v2 at v2's threshold of 0.9, a difference
  of 0.014, inside its 0.02 limit.
- The mismatches come from contracts the cap didn't touch. They sit in 7 contracts; the one of
  them with a capped request (Coherus) accounts for only 2. Two other contracts gained 35 and 36
  findings with no request anywhere near its cap.
- The 95% limit was set assuming Ollama is near-deterministic at temperature 0 with a fixed
  seed. That assumption was wrong: the same prompts got different answers in two runs. I
  accepted v2 for the selection on that basis, since the F2 gap was inside its limit. A rerun of v2 on the same 23
  contracts, with nothing changed, measures how much two identical runs differ (below).
- The hybrid did reproduce: hybrid v1 and v2 agree on all 5,146 findings, with the same scores.
  Its answers are short lists of clause types (the longest was 239 tokens), while the LLM-only
  answers are long lists of quotes. llm-qwen7b-v1 also ran for hours with 1 GB of RAM or less
  free, which may change how Ollama splits the model between GPU and CPU. Both are guesses at
  why one reproduced and the other didn't; I haven't tested either.

### What v2's request log shows

- 344 requests. My prompt count matched Ollama's on all of them. No request timed out; the
  slowest took 156.5 s.
- 4 requests (1.2%) hit their cap, each ending in 133 to 157 s, all four cut inside a
  half-written item: CoherusBiosciences chunk 72,797-84,424 (2,118 tokens, 23 whole items kept),
  EdietsCom chunk 30,891-42,642 (v1's failing contract; 2,091 tokens, 12 items but only 4
  distinct after merging), IMAGEWARESYSTEMS chunk 0-11,937 (2,383 tokens, 33 items) and
  LegacyEducationAlliance chunk 9,870-19,603 (2,482 tokens, 15 items, 3 distinct). The EdietsCom
  and Legacy answers mostly repeat themselves, so little was lost; the Coherus and Imageware
  chunks list many clause types, so the cut may have lost some findings there.
- The longest answer that ended by itself was 2,008 tokens, against a cap of 2,515 for that
  request (prompt 3,613 tokens). The closest any answer came to its cap was 1,763 of 1,860. The
  median answer was 280 tokens and the 95th percentile 1,350. A margin of 3 times the longest
  answer (about 6,000 tokens) would not fit in the window at all; the per-request cap instead
  never cuts an answer that fits.

### v2 against itself

llm-qwen7b-v2 was run again on the same 23 contracts with nothing changed (same code, model,
prompts, cap, temperature 0 and seed), as `llm-qwen7b-v2-rerun`. The comparison is in
`reports/compare_llm-qwen7b-v2_llm-qwen7b-v2-rerun.md`.

- 90.7% of findings match (824 in both, 25 only in the first run, 59 only in the rerun).
- High-stakes found F2 is 0.389 for the first run and 0.374 for the rerun at threshold 0.9, a
  difference of 0.015.
- The rerun made 154 requests. One hit its cap, the same Coherus chunk (72,797-84,424) at the
  same length (2,118 tokens, 23 whole items) as in v2. The slowest request took 127.1 s.

So two identical runs differ about as much as v1 and v2 did (87.2% matching, a 0.014 gap). The
gap between v1 and v2 is about the size of the local LLM's own run-to-run noise, which supports
using v2. It also means my 95% matching limit was never reachable for the LLM alone on this
setup; a limit for future runs should be set from this rerun, not assumed.

## Test results

CUAD's 102 test contracts, run once on 30 October 2026, after the selection above was written
down. Each method uses the threshold it got on validation (keywords 0.5, QA 0.1, hybrid 0.15) and
at most 2 quotes per type. The numbers are from `experiments/results/test-*.json`, with 95%
bootstrap intervals over contracts (1,000 resamples).

| Method | High-stakes found F2 | Findings per contract | Span AUPR | Seconds per contract |
|---|---:|---:|---:|---:|
| Keywords | 0.500 (0.432-0.568) | 16.2 | 0.321 | 0.1 |
| QA, 4 epochs, seed 0 | 0.752 (0.708-0.787) | 35.8 | 0.378 | 48.2 |
| Hybrid, qwen7b v2 (selected) | 0.745 (0.698-0.782) | 35.3 | 0.427 | 77.6 |

Other numbers from the same files:

- High-stakes found recall: keywords 0.503, QA 0.916, hybrid 0.898.
- Micro found F2 over all 41 types: keywords 0.493, QA 0.740, hybrid 0.766.
- Grounding rejected no quotes for any of the three (4,436, 83,620 and 7,496 submitted).
- The hybrid's time includes 330 s it spent paused waiting for free memory.

Said plainly:

- The selected hybrid did not beat QA alone on the main measure. Its high-stakes found F2 is
  0.007 lower, and the two intervals almost coincide. On validation it was 0.017 higher, also
  within error, so the small edge the selection rested on did not hold on test.
- QA alone is about 1.6 times faster (48.2 s against 77.6 s per contract) and needs no LLM.
- The hybrid is better at ranking quotes (span AUPR 0.427 against 0.378) and slightly better
  over all 41 types (micro found F2 0.766 against 0.740), with a few fewer findings per contract.
  These are not the measure the selection was made on.
- Both models are far ahead of keywords (about 0.25 found F2 higher), which matches validation.
- Keywords did a little better on test than on validation (0.500 against 0.445); QA and the
  hybrid did a little worse (0.752 against 0.763, 0.745 against 0.780).
- The LLM alone was not run on test. It would take about 4.5 hours here, over the 3-hour limit
  I work to without asking, and on validation it was well behind the others.

## Notes

- Price Restrictions has no test contracts (13 train, 2 validation, 0 test), so it has no test
  score; the CUAD paper notes the same. It is still trained on and scored on validation.
- DeBERTa-v3-base was timed but not trained: 3.105 s per optimiser step (4 x 8 windows), peak
  GPU memory 5.60 GB of 6, so about 0.70 hours per epoch and 2.8 hours for 4 epochs. It is a
  next step, not part of this comparison.
- A hosted LLM (method 5) was not run, because it costs money.
