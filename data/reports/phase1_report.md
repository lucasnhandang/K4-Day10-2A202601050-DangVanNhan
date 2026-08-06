# Phase 1 Baseline Report

## Source and artifacts
- Source: `Crossref REST API`
- Query: `agentic retrieval augmented generation large language model`
- Filter: `from-pub-date:2026-02-07,has-abstract:true`
- Raw records: 24
- Clean records: 24
- Raw response: `data/raw/crossref_response.json`
- Raw records: `data/raw/crossref_records.json`
- Clean CSV: `data/clean/papers_clean.csv`
- Embedding manifest: `data/embeddings/papers_embeddings.json`
- Frozen test set: `data/eval/test_set.json`

## Evaluation metrics
- Samples: 10
- Retrieval hit rate: 90.00%
- Mean token F1: 0.1930
- Judge accuracy: 60.00%
- Mean judge score: 3.40/5
- Ragas: `{'skipped': 'Set RUN_RAGAS=1 to enable the slower Ragas pass.'}`

## Data quality
- Status: PASS
- Checks: 12 passed, 0 failed
- Failed checks: none
- Quality artifact: `data/quality/baseline_quality.json`

## Freshness
- Status: fresh
- Fresh: True
- Threshold: 180 days
- Stale rows: 0
- Latest publication: 2026-08-01
- Freshness artifact: `data/quality/freshness_report.json`

## Result artifacts
- Metrics: `data/results/baseline_metrics.json`
- Per-question answers: `data/results/baseline_answers.json`
