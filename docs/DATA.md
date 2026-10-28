# Data

## Source

ClauseScout is trained and evaluated on the **Contract Understanding Atticus Dataset (CUAD) v1**,
created by [The Atticus Project](https://www.atticusprojectai.org/cuad).

- 510 commercial contracts from SEC EDGAR filings, labelled by law students and checked by
  experienced lawyers for 41 clause types.
- Annotations and the official 408/102 train/test split come from `data.zip` in the
  [CUAD GitHub repo](https://github.com/TheAtticusProject/cuad)
  (`train_separate_questions.json`, `test.json`).
- The contract PDFs, plain texts and `master_clauses.csv` come from `CUAD_v1.zip` in the
  [Zenodo record](https://zenodo.org/records/4595826) linked from the Atticus Project site.
  The GitHub repo only holds the JSON annotations.

`scripts/download_data.py` fetches both into `data/raw/` (gitignored) and checks the Zenodo
archive's md5. The contract text inside the master JSON is identical to the text in the
official test JSON for all 102 test contracts, so I use the master JSON as the single source
of contract text and gold spans.

## Licence

CUAD is released under the [Creative Commons Attribution 4.0 (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/)
licence. This repo does not redistribute the dataset; it downloads it from the official sources.

## Citation

> Dan Hendrycks, Collin Burns, Anya Chen and Spencer Ball. *CUAD: An Expert-Annotated NLP
> Dataset for Legal Contract Review.* NeurIPS 2021 Datasets and Benchmarks Track.
> [arXiv:2103.06268](https://arxiv.org/abs/2103.06268)

```bibtex
@article{hendrycks2021cuad,
  title   = {CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review},
  author  = {Dan Hendrycks and Collin Burns and Anya Chen and Spencer Ball},
  journal = {NeurIPS},
  year    = {2021}
}
```

## Splits

| Split | Contracts | Source |
|---|---:|---|
| train | 346 | official training contracts, minus validation |
| val | 62 | about 15% of the official training contracts |
| test | 102 | the official CUAD test contracts, used once at the end |

The ID lists are committed in `experiments/splits/` and produced by `scripts/make_split.py`
(seed 13). Validation is split by contract, never by window or clause, so no contract
appears in both train and validation. I used iterative stratification (Sechidis, Tsoumakas
and Vlahavas, 2011) over the 41 clause types plus a contract-length quartile, so every clause
type has at least two validation contracts and the validation length distribution matches
train.

A first attempt that filled validation greedily from the rarest type upwards over-sampled
rare types (30 to 40% of their contracts in validation) and long contracts, because contracts
with rare clauses tend to be long. I replaced it before using the split for anything.

Full statistics are in [reports/data_stats.md](../reports/data_stats.md). One thing to know
when reading results: Price Restrictions has no test contracts, which the CUAD paper also
notes, so it is excluded from test-set per-category tables.
