# llm-qwen7b-v1 against llm-qwen7b-v2 on the contracts both finished

23 validation contracts; threshold 0.9 (from llm-qwen7b-v2 unless set by hand); top 2 quotes per type, as in rule 2.

| | Raw findings | Grounded findings | High-stakes found F2 |
|---|---:|---:|---:|
| llm-qwen7b-v1 | 785 | 574 | 0.403 (0.303-0.494) |
| llm-qwen7b-v2 | 849 | 570 | 0.389 (0.286-0.484) |

Findings in both runs (same contract, type and quote): 761; only in llm-qwen7b-v1: 24; only in llm-qwen7b-v2: 88. Share matching: 87.2%.
Difference in high-stakes found F2: 0.014.

Expected beforehand: at least 95% matching and a found F2 gap of at most 0.02. Outside the limits I set beforehand; see the experiment report.
