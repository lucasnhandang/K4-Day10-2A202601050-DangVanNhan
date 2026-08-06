from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd

from core.config import load_settings
from core.utils import read_json
from observability.quality import build_freshness_report, run_data_quality_checks


def _clean_dataframe() -> pd.DataFrame:
    run_date = datetime(2026, 8, 6, tzinfo=UTC)
    rows = []
    for index, age_days in enumerate((20, 45, 75, 120), start=1):
        summary = (
            f"This is a sufficiently detailed scholarly summary for document {index} "
            "that supports deterministic data-quality validation."
        )
        published = (run_date - timedelta(days=age_days)).date().isoformat()
        rows.append(
            {
                "paper_id": f"10-0000-test-{index:03d}",
                "title": f"Test Paper {index}",
                "summary": summary,
                "authors_joined": f"Author {index}",
                "categories_joined": "Data Quality",
                "published": published,
                "age_days": float(age_days),
                "summary_chars": len(summary),
                "text_for_embedding": f"Title: Test Paper {index} | Summary: {summary}",
            }
        )
    return pd.DataFrame(rows)


def test_clean_dataframe_passes_quality_checks(tmp_path) -> None:
    settings = load_settings(project_dir=tmp_path)

    result = run_data_quality_checks(_clean_dataframe(), settings, "baseline_quality")

    assert result["success"] is True
    assert result["failed_checks"] == 0
    assert result["total_rows"] == 4
    persisted = read_json(settings.paths.quality_dir / "baseline_quality.json")
    assert persisted == result


def test_corruption_is_detected(tmp_path) -> None:
    settings = load_settings(project_dir=tmp_path)
    corrupted = _clean_dataframe()
    corrupted.loc[0, "summary"] = ""
    corrupted.loc[1, "text_for_embedding"] = " "
    corrupted.loc[2, "age_days"] = settings.freshness_threshold_days + 1
    corrupted = pd.concat([corrupted, corrupted.iloc[[3]]], ignore_index=True)

    result = run_data_quality_checks(corrupted, settings, "corrupted_quality")
    checks = {check["name"]: check for check in result["checks"]}

    assert result["success"] is False
    assert checks["paper_id_unique"]["success"] is False
    assert checks["summary_not_blank"]["success"] is False
    assert checks["summary_chars_consistent"]["success"] is False
    assert checks["text_for_embedding_not_blank"]["success"] is False
    assert checks["age_days_within_freshness_threshold"]["success"] is False


def test_missing_contract_columns_fail_without_crashing(tmp_path) -> None:
    settings = load_settings(project_dir=tmp_path)

    result = run_data_quality_checks(pd.DataFrame({"paper_id": ["one", "two", "three"]}), settings, "missing")

    assert result["success"] is False
    required_check = next(check for check in result["checks"] if check["name"] == "required_columns_present")
    assert "summary" in required_check["observed_value"]


def test_freshness_report_for_fresh_data(tmp_path) -> None:
    settings = load_settings(project_dir=tmp_path)
    output_path = settings.paths.quality_dir / "freshness_report.json"

    result = build_freshness_report(_clean_dataframe(), settings, output_path)

    assert result["is_fresh"] is True
    assert result["status"] == "fresh"
    assert result["stale_rows"] == 0
    assert result["latest_published"] == "2026-07-17"
    assert result["oldest_published"] == "2026-04-08"
    assert read_json(output_path) == result


def test_freshness_report_detects_stale_and_invalid_rows(tmp_path) -> None:
    settings = load_settings(project_dir=tmp_path)
    dataframe = _clean_dataframe()
    dataframe.loc[0, "published"] = "not-a-date"
    dataframe.loc[1, "age_days"] = settings.freshness_threshold_days + 10

    result = build_freshness_report(
        dataframe,
        settings,
        settings.paths.quality_dir / "corrupted_freshness.json",
    )

    assert result["is_fresh"] is False
    assert result["status"] == "invalid"
    assert result["invalid_published_rows"] == 1
    assert result["stale_rows"] == 1


def test_empty_dataframe_has_unknown_freshness(tmp_path) -> None:
    settings = load_settings(project_dir=tmp_path)

    result = build_freshness_report(
        pd.DataFrame(),
        settings,
        settings.paths.quality_dir / "empty_freshness.json",
    )

    assert result["is_fresh"] is False
    assert result["status"] == "unknown"
    assert result["latest_published"] is None
    assert result["oldest_published"] is None
