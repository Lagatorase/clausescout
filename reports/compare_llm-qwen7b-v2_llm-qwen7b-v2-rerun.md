# llm-qwen7b-v2 against llm-qwen7b-v2-rerun on the contracts both finished

23 validation contracts; threshold 0.9 (from llm-qwen7b-v2-rerun unless set by hand); top 2 quotes per type, as in rule 2.

| | Raw findings | Grounded findings | High-stakes found F2 |
|---|---:|---:|---:|
| llm-qwen7b-v2 | 849 | 570 | 0.389 (0.286-0.484) |
| llm-qwen7b-v2-rerun | 883 | 574 | 0.374 (0.273-0.470) |

Findings in both runs (same contract, type and quote): 824; only in llm-qwen7b-v2: 25; only in llm-qwen7b-v2-rerun: 59. Share matching: 90.7%.
Difference in high-stakes found F2: 0.015.

Expected beforehand: at least 95% matching and a found F2 gap of at most 0.02. Outside the limits I set beforehand; see the experiment report.
