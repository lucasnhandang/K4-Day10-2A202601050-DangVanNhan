"""Ablation test: run each corruption scenario independently and compare impact.

Each scenario is applied in isolation so we can measure its individual
contribution to retrieval/answer degradation — something the combined
corruption flow cannot tell us.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from core.config import Settings, load_settings
from core.utils import read_json, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.corruption import VALID_SCENARIOS, corrupt_clean_dataframe
from retrieval.index import LocalEmbeddingIndex
from observability.reporting import generate_ablation_report


def _load_target_ids(settings: Settings) -> set[str]:
    test_set = read_json(settings.paths.eval_testset)
    if not isinstance(test_set, list) or not test_set:
        raise ValueError(f"Frozen test set is invalid or empty: {settings.paths.eval_testset}")
    return {
        str(paper_id)
        for item in test_set
        if isinstance(item, dict)
        for paper_id in item.get("ground_truth_doc_ids", [])
        if str(paper_id).strip()
    }


def _run_single_scenario(
    settings: Settings,
    clean_df: pd.DataFrame,
    target_ids: set[str],
    scenario: str,
    baseline_metrics: dict[str, Any],
    ablation_dir: Path,
) -> dict[str, Any]:
    """Corrupt with one scenario, evaluate, return metrics + delta."""
    log_path = ablation_dir / f"ablation_{scenario}_log.json"
    metrics_path = ablation_dir / f"ablation_{scenario}_metrics.json"
    answers_path = ablation_dir / f"ablation_{scenario}_answers.json"
    embeddings_path = ablation_dir / f"ablation_{scenario}_embeddings.json"

    corrupted_df = corrupt_clean_dataframe(
        clean_df,
        log_path,
        target_paper_ids=target_ids,
        reference_time=datetime.now(),
        scenarios=[scenario],
    )

    index = LocalEmbeddingIndex.build(
        df=corrupted_df,
        settings=settings,
        embeddings_output_path=embeddings_path,
    )

    evaluation = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=metrics_path,
        answers_output_path=answers_path,
    )

    metrics = evaluation.summary
    delta = {}
    for key in ("retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"):
        baseline_val = baseline_metrics.get(key, 0)
        corrupted_val = metrics.get(key, 0)
        delta[key] = round(corrupted_val - baseline_val, 6) if isinstance(baseline_val, (int, float)) else None

    return {
        "scenario": scenario,
        "corrupted_rows": len(corrupted_df),
        "metrics": metrics,
        "delta": delta,
        "metrics_path": str(metrics_path),
        "answers_path": str(answers_path),
    }


def main() -> dict[str, Any]:
    """Run ablation: each corruption scenario in isolation."""
    settings = load_settings()
    baseline_metrics = read_json(settings.paths.baseline_metrics)
    clean_df = pd.read_csv(settings.paths.clean_csv)
    target_ids = _load_target_ids(settings)

    ablation_dir = settings.paths.quality_dir / "ablation"
    ablation_dir.mkdir(parents=True, exist_ok=True)

    print("[ablation] Running each corruption scenario independently...\n")
    results: dict[str, dict[str, Any]] = {}

    for scenario in sorted(VALID_SCENARIOS):
        print(f"  → {scenario}")
        result = _run_single_scenario(
            settings, clean_df, target_ids, scenario, baseline_metrics, ablation_dir,
        )
        results[scenario] = result
        dr = result["delta"].get("retrieval_hit_rate", 0)
        print(f"    corrupted_rows={result['corrupted_rows']}, retrieval_delta={dr:+.2%}")

    summary_path = ablation_dir / "ablation_summary.json"
    write_json(summary_path, {
        "baseline_metrics": baseline_metrics,
        "scenarios": results,
    })

    print(f"\n[ablation] Summary: {summary_path}")
    print("[ablation] Generating ablation report...")
    generate_ablation_report(
        report_path=settings.paths.ablation_report,
        baseline_metrics=baseline_metrics,
        scenario_results=results,
    )
    print(f"[ablation] Report: {settings.paths.ablation_report}")

    return {"baseline": baseline_metrics, "scenarios": results}
