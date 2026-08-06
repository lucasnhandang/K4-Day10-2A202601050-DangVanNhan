from __future__ import annotations

from pathlib import Path
from typing import Any

from core.utils import write_text

# ---------------------------------------------------------------------------
# Scenario display names
# ---------------------------------------------------------------------------

_SCENARIO_LABELS = {
    "blank_summary": "Xoá summary",
    "stale_date": "Làm cũ ngày",
    "add_noise": "Thêm noise",
    "duplicates": "Tạo duplicate",
}

_METRIC_KEYS = (
    ("retrieval_hit_rate", "Retrieval hit rate", ".2%"),
    ("mean_token_f1", "Mean token F1", ".4f"),
    ("judge_accuracy", "Judge accuracy", ".2%"),
    ("mean_judge_score", "Mean judge score", ".2f"),
)


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Persist an evidence-linked Markdown report for the baseline run."""
    path = Path(report_path)
    checks = quality.get("checks", [])
    failed_checks = [check["name"] for check in checks if not check.get("success")]
    ragas = metrics.get("ragas", {})

    lines = [
        "# Phase 1 Baseline Report",
        "",
        "## Source and artifacts",
        f"- Source: `{source_summary.get('source_api', 'unknown')}`",
        f"- Query: `{source_summary.get('query', '')}`",
        f"- Filter: `{source_summary.get('filter', '')}`",
        f"- Raw records: {source_summary.get('raw_records', 0)}",
        f"- Clean records: {source_summary.get('clean_records', 0)}",
        f"- Raw response: `{source_summary.get('raw_response_path', '')}`",
        f"- Raw records: `{source_summary.get('raw_records_path', '')}`",
        f"- Clean CSV: `{source_summary.get('clean_csv_path', '')}`",
        f"- Embedding manifest: `{source_summary.get('embedding_manifest_path', '')}`",
        f"- Frozen test set: `{source_summary.get('test_set_path', '')}`",
        "",
        "## Evaluation metrics",
        f"- Samples: {metrics.get('samples', 0)}",
        f"- Retrieval hit rate: {metrics.get('retrieval_hit_rate', 0.0):.2%}",
        f"- Mean token F1: {metrics.get('mean_token_f1', 0.0):.4f}",
        f"- Judge accuracy: {metrics.get('judge_accuracy', 0.0):.2%}",
        f"- Mean judge score: {metrics.get('mean_judge_score', 0.0):.2f}/5",
        f"- Ragas: `{ragas}`",
        "",
        "## Data quality",
        f"- Status: {'PASS' if quality.get('success') else 'FAIL'}",
        f"- Checks: {quality.get('passed_checks', 0)} passed, {quality.get('failed_checks', 0)} failed",
        f"- Failed checks: {', '.join(failed_checks) if failed_checks else 'none'}",
        f"- Quality artifact: `{quality.get('report_path', '')}`",
        "",
        "## Freshness",
        f"- Status: {freshness.get('status', 'unknown')}",
        f"- Fresh: {freshness.get('is_fresh', False)}",
        f"- Threshold: {freshness.get('threshold_days', 'unknown')} days",
        f"- Stale rows: {freshness.get('stale_rows', 0)}",
        f"- Latest publication: {freshness.get('latest_published') or 'unknown'}",
        f"- Freshness artifact: `{freshness.get('report_path', '')}`",
        "",
        "## Result artifacts",
        "- Metrics: `data/results/baseline_metrics.json`",
        "- Per-question answers: `data/results/baseline_answers.json`",
    ]
    write_text(path, "\n".join(lines) + "\n")


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    """Write an evidence-linked comparison across baseline, corruption and repair."""
    path = Path(report_path)
    metric_keys = (
        ("retrieval_hit_rate", "Retrieval hit rate", ".2%"),
        ("mean_token_f1", "Mean token F1", ".4f"),
        ("judge_accuracy", "Judge accuracy", ".2%"),
        ("mean_judge_score", "Mean judge score", ".2f"),
    )

    def metric_value(metrics: dict[str, Any], key: str, format_spec: str) -> str:
        value = metrics.get(key)
        return format(float(value), format_spec) if isinstance(value, (int, float)) else "n/a"

    def failed_checks(quality: dict[str, Any]) -> str:
        failures = [item["name"] for item in quality.get("checks", []) if not item.get("success")]
        return ", ".join(failures) if failures else "none"

    rows = [
        "# Phase 2 Corruption, Repair, and Comparison Report",
        "",
        "## Evaluation contract",
        "- Frozen test set: `data/eval/test_set.json` (reused without regeneration)",
        "- Repair source: `data/raw/crossref_records.json` (not the corrupted CSV)",
        "- Corruption log: `data/results/corruption_log.json`",
        "",
        "## Metrics",
        "| Metric | Baseline | Corrupted | Repaired |",
        "| --- | ---: | ---: | ---: |",
    ]
    for key, label, format_spec in metric_keys:
        rows.append(
            "| {} | {} | {} | {} |".format(
                label,
                metric_value(baseline_metrics, key, format_spec),
                metric_value(corrupted_metrics, key, format_spec),
                metric_value(repaired_metrics, key, format_spec),
            )
        )

    rows.extend(
        [
            "",
            "## Data quality and freshness",
            "| State | Quality | Failed checks | Freshness | Stale rows |",
            "| --- | --- | --- | --- | ---: |",
            "| Corrupted | {} | {} | {} | {} |".format(
                "PASS" if corrupted_quality.get("success") else "FAIL",
                failed_checks(corrupted_quality),
                corrupted_freshness.get("status", "unknown"),
                corrupted_freshness.get("stale_rows", "n/a"),
            ),
            "| Repaired | {} | {} | {} | {} |".format(
                "PASS" if repaired_quality.get("success") else "FAIL",
                failed_checks(repaired_quality),
                repaired_freshness.get("status", "unknown"),
                repaired_freshness.get("stale_rows", "n/a"),
            ),
            "",
            "## Artifacts",
            "- Corrupted CSV/JSON: `data/clean/papers_clean_corrupted.csv`, `data/clean/papers_clean_corrupted.json`",
            "- Repaired CSV/JSON: `data/clean/papers_clean_repaired.csv`, `data/clean/papers_clean_repaired.json`",
            "- Metrics and answers: `data/results/corrupted_*.json`, `data/results/repaired_*.json`",
            "- Quality and freshness: `data/quality/corrupted_*.json`, `data/quality/repaired_*.json`",
            "",
            "Metrics are recorded evidence; any degradation or recovery claim must follow the values above.",
        ]
    )
    write_text(path, "\n".join(rows) + "\n")


def generate_ablation_report(
    report_path,
    baseline_metrics: dict[str, Any],
    scenario_results: dict[str, dict[str, Any]],
) -> None:
    """Write a Markdown report comparing each corruption scenario against baseline."""
    path = Path(report_path)

    def _fmt(metrics: dict[str, Any], key: str, spec: str) -> str:
        value = metrics.get(key)
        return format(float(value), spec) if isinstance(value, (int, float)) else "n/a"

    rows = [
        "# Ablation Report — Per-Scenario Corruption Impact",
        "",
        "Each scenario is applied **in isolation** against the frozen test set.",
        "Delta = scenario metric minus baseline metric.",
        "",
        "## Baseline",
        f"- Retrieval hit rate: {_fmt(baseline_metrics, 'retrieval_hit_rate', '.2%')}",
        f"- Mean token F1: {_fmt(baseline_metrics, 'mean_token_f1', '.4f')}",
        f"- Judge accuracy: {_fmt(baseline_metrics, 'judge_accuracy', '.2%')}",
        f"- Mean judge score: {_fmt(baseline_metrics, 'mean_judge_score', '.2f')}/5",
        "",
        "## Per-Scenario Results",
    ]

    # Metrics table
    header = "| Metric | Baseline |"
    separator = "| --- | ---: |"
    for scenario in sorted(scenario_results.keys()):
        label = _SCENARIO_LABELS.get(scenario, scenario)
        header += f" {label} |"
        separator += " ---: |"
    rows.append(header)
    rows.append(separator)

    for key, label, spec in _METRIC_KEYS:
        line = f"| {label} | {_fmt(baseline_metrics, key, spec)} |"
        for scenario in sorted(scenario_results.keys()):
            metrics = scenario_results[scenario].get("metrics", {})
            line += f" {_fmt(metrics, key, spec)} |"
        rows.append(line)

    # Delta table
    rows.extend([
        "",
        "## Delta (Scenario − Baseline)",
    ])
    delta_header = "| Metric |"
    delta_sep = "| --- |"
    for scenario in sorted(scenario_results.keys()):
        label = _SCENARIO_LABELS.get(scenario, scenario)
        delta_header += f" {label} |"
        delta_sep += " ---: |"
    rows.append(delta_header)
    rows.append(delta_sep)

    for key, label, spec in _METRIC_KEYS:
        line = f"| {label} |"
        for scenario in sorted(scenario_results.keys()):
            delta = scenario_results[scenario].get("delta", {})
            val = delta.get(key)
            if val is None:
                line += " n/a |"
            else:
                sign = "+" if val > 0 else ""
                line += f" {sign}{format(float(val), spec)} |"
        rows.append(line)

    # Worst scenario identification
    rows.extend(["", "## Worst-Case Scenario per Metric"])
    for key, label, spec in _METRIC_KEYS:
        worst_scenario = None
        worst_delta = 0
        for scenario, result in scenario_results.items():
            d = result.get("delta", {}).get(key)
            if d is not None and d < worst_delta:
                worst_delta = d
                worst_scenario = scenario
        if worst_scenario:
            label_cn = _SCENARIO_LABELS.get(worst_scenario, worst_scenario)
            rows.append(f"- **{label}**: {label_cn} ({worst_delta:+.4f})")
        else:
            rows.append(f"- **{label}**: no degradation detected")

    rows.extend([
        "",
        "## Artifacts",
        "- Ablation logs: `data/quality/ablation/ablation_*_log.json`",
        "- Per-scenario metrics: `data/quality/ablation/ablation_*_metrics.json`",
        "- Per-scenario answers: `data/quality/ablation/ablation_*_answers.json`",
        "- Summary: `data/quality/ablation/ablation_summary.json`",
        "",
        "Metrics are recorded evidence; each row isolates exactly one corruption scenario.",
    ])
    write_text(path, "\n".join(rows) + "\n")
