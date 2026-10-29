# hybrid-qwen7b-v1 against hybrid-qwen7b-v2 on the contracts both finished

62 validation contracts; threshold 0.15 (from hybrid-qwen7b-v2 unless set by hand); top 2 quotes per type, as in rule 2.

| | Raw findings | Grounded findings | High-stakes found F2 |
|---|---:|---:|---:|
| hybrid-qwen7b-v1 | 5145 | 5146 | 0.780 (0.717-0.833) |
| hybrid-qwen7b-v2 | 5145 | 5146 | 0.780 (0.717-0.833) |

Findings in both runs (same contract, type and quote): 5145; only in hybrid-qwen7b-v1: 0; only in hybrid-qwen7b-v2: 0. Share matching: 100.0%.
Difference in high-stakes found F2: 0.000.

Expected beforehand: at least 95% matching and a found F2 gap of at most 0.02. Within that, so v2 can stand in for v1.
