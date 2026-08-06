"""Baseline pipeline for the clean Crossref paper corpus.

The pipeline deliberately rebuilds the cleaned dataset and vector index from
the raw snapshot on every run.  The source snapshot and evaluation set are
reused by default, which keeps normal runs reproducible and avoids needless
external API calls.  Set ``REFRESH_SOURCE=true`` or ``REFRESH_TEST_SET=true``
to replace either artifact.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from core.config import Settings, load_settings
from core.utils import project_relative_path, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def _persist_clean_data(clean_df, settings: Settings) -> None:
    """Save the single cleaned-data source of truth in both supported formats."""
    write_csv(clean_df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, clean_df.to_dict(orient="records"))


def _load_or_build_test_set(clean_df, settings: Settings) -> list[dict[str, Any]]:
    """Load the frozen evaluation set unless an explicit refresh was requested."""
    if settings.paths.eval_testset.exists() and not settings.refresh_test_set:
        test_set = read_json(settings.paths.eval_testset)
        if not isinstance(test_set, list) or not test_set:
            raise ValueError(
                f"Frozen test set is invalid or empty: {settings.paths.eval_testset}. "
                "Set REFRESH_TEST_SET=true to rebuild it."
            )
        return test_set
    return build_test_set(clean_df, settings.paths.eval_testset)


def _source_summary(settings: Settings, raw_record_count: int, clean_count: int) -> dict[str, Any]:
    relative = lambda path: project_relative_path(path, settings.paths.project_dir)
    return {
        "source_api": settings.source_api,
        "query": settings.source_query,
        "filter": settings.source_filter,
        "raw_records": raw_record_count,
        "clean_records": clean_count,
        "raw_response_path": relative(settings.paths.raw_api_response),
        "raw_records_path": relative(settings.paths.raw_records_json),
        "clean_csv_path": relative(settings.paths.clean_csv),
        "clean_json_path": relative(settings.paths.clean_json),
        "embedding_manifest_path": relative(settings.paths.embeddings_json),
        "test_set_path": relative(settings.paths.eval_testset),
    }


def main() -> dict[str, Any]:
    """Run the clean-data baseline and return the generated metric summary."""
    settings = load_settings()

    print("[1/8] Loading Crossref records...")
    records = fetch_source_records(settings)
    print(f"      {len(records)} raw records available.")

    print("[2/8] Cleaning records and saving clean artifacts...")
    clean_df = build_clean_dataframe(records, run_date=datetime.now())
    if clean_df.empty:
        raise ValueError("Cleaning produced no usable records; baseline evaluation cannot run.")
    _persist_clean_data(clean_df, settings)
    print(f"      {len(clean_df)} clean records saved.")

    print("[3/8] Building the ChromaDB vector index...")
    index = LocalEmbeddingIndex.build(
        df=clean_df,
        settings=settings,
        embeddings_output_path=settings.paths.embeddings_json,
    )
    print(f"      {len(index.documents)} documents indexed.")

    print("[4/8] Loading or freezing the evaluation test set...")
    test_set = _load_or_build_test_set(clean_df, settings)
    print(f"      {len(test_set)} evaluation questions ready.")

    print("[5/8] Answering evaluation questions and calculating metrics...")
    evaluation = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )
    metrics = evaluation.summary
    print(
        "      retrieval_hit_rate={:.2%}, mean_token_f1={:.4f}".format(
            metrics["retrieval_hit_rate"], metrics["mean_token_f1"]
        )
    )

    print("[6/8] Running data-quality checks...")
    quality = run_data_quality_checks(clean_df, settings, "baseline_quality")
    print(f"      quality success={quality['success']} ({quality['failed_checks']} failed checks).")

    print("[7/8] Building freshness report...")
    freshness = build_freshness_report(clean_df, settings, settings.paths.freshness_report)
    print(f"      freshness status={freshness['status']}.")

    print("[8/8] Writing the baseline Markdown report...")
    generate_phase1_report(
        report_path=settings.paths.baseline_report,
        source_summary=_source_summary(settings, len(records), len(clean_df)),
        metrics=metrics,
        quality=quality,
        freshness=freshness,
    )
    print(f"      Report: {settings.paths.baseline_report}")

    return metrics


if __name__ == "__main__":
    main()
