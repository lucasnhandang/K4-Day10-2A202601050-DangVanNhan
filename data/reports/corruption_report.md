# Phase 2 Corruption, Repair, and Comparison Report

## Evaluation contract
- Frozen test set: `data/eval/test_set.json` (reused without regeneration)
- Repair source: `data/raw/crossref_records.json` (not the corrupted CSV)
- Corruption log: `data/results/corruption_log.json`

## Metrics
| Metric | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
| Retrieval hit rate | 90.00% | 70.00% | 90.00% |
| Mean token F1 | 0.1930 | 0.1717 | 0.1981 |
| Judge accuracy | 60.00% | 50.00% | 60.00% |
| Mean judge score | 3.40 | 3.00 | 3.50 |

## Data quality and freshness
| State | Quality | Failed checks | Freshness | Stale rows |
| --- | --- | --- | --- | ---: |
| Corrupted | FAIL | paper_id_unique, summary_not_blank, summary_minimum_length, age_days_within_freshness_threshold | stale | 2 |
| Repaired | PASS | none | fresh | 0 |

## Artifacts
- Corrupted CSV/JSON: `data/clean/papers_clean_corrupted.csv`, `data/clean/papers_clean_corrupted.json`
- Repaired CSV/JSON: `data/clean/papers_clean_repaired.csv`, `data/clean/papers_clean_repaired.json`
- Metrics and answers: `data/results/corrupted_*.json`, `data/results/repaired_*.json`
- Quality and freshness: `data/quality/corrupted_*.json`, `data/quality/repaired_*.json`

Metrics are recorded evidence; any degradation or recovery claim must follow the values above.
