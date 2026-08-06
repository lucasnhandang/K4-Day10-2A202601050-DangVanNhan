from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Any

import pandas as pd

from core.config import Settings, load_settings
from core.utils import read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


def _load_frozen_target_ids(settings: Settings) -> set[str]:
    test_set = read_json(settings.paths.eval_testset)
    if not isinstance(test_set, list) or not test_set:
        raise ValueError(f"Frozen test set is invalid or empty: {settings.paths.eval_testset}")

    target_ids = {
        str(paper_id)
        for item in test_set
        if isinstance(item, dict)
        for paper_id in item.get("ground_truth_doc_ids", [])
        if str(paper_id).strip()
    }
    if not target_ids:
        raise ValueError("Frozen test set contains no ground_truth_doc_ids.")
    return target_ids


def _persist_dataframe(dataframe: pd.DataFrame, csv_path, json_path) -> None:
    write_csv(dataframe, csv_path)
    write_json(json_path, dataframe.to_dict(orient="records"))


def _evaluate(settings: Settings, dataframe: pd.DataFrame, embeddings_path, metrics_path, answers_path):
    index = LocalEmbeddingIndex.build(
        df=dataframe,
        settings=settings,
        embeddings_output_path=embeddings_path,
    )
    return evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=metrics_path,
        answers_output_path=answers_path,
    )


def _require_phase1_artifacts(settings: Settings) -> None:
    required_paths = {
        "clean CSV": settings.paths.clean_csv,
        "baseline metrics": settings.paths.baseline_metrics,
        "frozen test set": settings.paths.eval_testset,
        "raw records snapshot": settings.paths.raw_records_json,
    }
    missing = [f"{label}: {path}" for label, path in required_paths.items() if not path.exists()]
    if missing:
        raise FileNotFoundError("Phase 2 requires completed Phase 1 artifacts:\n" + "\n".join(missing))


def main() -> dict[str, Any]:
    """Run the corruption, evaluation, repair, and comparison experiment."""
    settings = load_settings()
    _require_phase1_artifacts(settings)

    # This experiment must consume the existing C2 evaluation contract, never
    # regenerate it.  The digest makes an accidental mutation detectable.
    frozen_before = settings.paths.eval_testset.read_bytes()
    frozen_digest = sha256(frozen_before).hexdigest()
    target_paper_ids = _load_frozen_target_ids(settings)
    baseline_metrics = read_json(settings.paths.baseline_metrics)
    clean_df = pd.read_csv(settings.paths.clean_csv)

    print("[1/8] Creating controlled corruption against frozen-test documents...")
    corrupted_df = corrupt_clean_dataframe(
        clean_df,
        settings.paths.corruption_log,
        target_paper_ids=target_paper_ids,
        reference_time=datetime.now(),
    )
    _persist_dataframe(
        corrupted_df,
        settings.paths.corrupted_clean_csv,
        settings.paths.corrupted_clean_json,
    )
    print(f"      {len(corrupted_df)} corrupted rows saved.")

    print("[2/8] Rebuilding the corrupted ChromaDB index and evaluating frozen C2...")
    corrupted_evaluation = _evaluate(
        settings,
        corrupted_df,
        settings.paths.corrupted_embeddings_json,
        settings.paths.corrupted_metrics,
        settings.paths.corrupted_answers,
    )
    corrupted_metrics = corrupted_evaluation.summary
    print("      retrieval_hit_rate={:.2%}, mean_token_f1={:.4f}".format(
        corrupted_metrics["retrieval_hit_rate"], corrupted_metrics["mean_token_f1"]
    ))

    print("[3/8] Measuring corrupted data quality and freshness...")
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted_quality")
    corrupted_freshness = build_freshness_report(
        corrupted_df,
        settings,
        settings.paths.quality_dir / "corrupted_freshness.json",
    )

    print("[4/8] Repairing only from the persisted raw Crossref snapshot...")
    raw_records = load_raw_records(settings.paths.raw_records_json)
    repaired_df = build_clean_dataframe(raw_records, run_date=datetime.now())
    if repaired_df.empty:
        raise ValueError("Repair from raw snapshot produced no usable records.")
    _persist_dataframe(
        repaired_df,
        settings.paths.repaired_clean_csv,
        settings.paths.repaired_clean_json,
    )
    print(f"      {len(repaired_df)} repaired rows saved.")

    print("[5/8] Rebuilding the repaired ChromaDB index and evaluating frozen C2...")
    repaired_evaluation = _evaluate(
        settings,
        repaired_df,
        settings.paths.repaired_embeddings_json,
        settings.paths.repaired_metrics,
        settings.paths.repaired_answers,
    )
    repaired_metrics = repaired_evaluation.summary
    print("      retrieval_hit_rate={:.2%}, mean_token_f1={:.4f}".format(
        repaired_metrics["retrieval_hit_rate"], repaired_metrics["mean_token_f1"]
    ))

    print("[6/8] Measuring repaired data quality and freshness...")
    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired_quality")
    repaired_freshness = build_freshness_report(
        repaired_df,
        settings,
        settings.paths.quality_dir / "repaired_freshness.json",
    )

    print("[7/8] Verifying that the frozen evaluation artifact was not changed...")
    frozen_after = settings.paths.eval_testset.read_bytes()
    if sha256(frozen_after).hexdigest() != frozen_digest or frozen_after != frozen_before:
        raise RuntimeError("Frozen test set changed during Phase 2; refusing to publish comparison.")
    print("      frozen test set unchanged.")

    print("[8/8] Writing the baseline/corrupted/repaired comparison report...")
    generate_corruption_report(
        report_path=settings.paths.comparison_report,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted_metrics,
        repaired_metrics=repaired_metrics,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
        corrupted_freshness=corrupted_freshness,
        repaired_freshness=repaired_freshness,
    )
    print(f"      Report: {settings.paths.comparison_report}")

    return {
        "baseline": baseline_metrics,
        "corrupted": corrupted_metrics,
        "repaired": repaired_metrics,
        "frozen_test_set_sha256": frozen_digest,
    }
