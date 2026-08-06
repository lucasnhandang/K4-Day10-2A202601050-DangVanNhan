from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import now_utc, project_relative_path, safe_slug, write_json


MIN_ROW_COUNT = 3
MIN_SUMMARY_CHARS = 50
REQUIRED_COLUMNS = {
    "paper_id",
    "title",
    "summary",
    "published",
    "age_days",
    "summary_chars",
    "text_for_embedding",
}


def _check(
    name: str,
    success: bool,
    observed_value: Any,
    expected: str,
    message: str = "",
) -> dict[str, Any]:
    """Build one JSON-serializable quality-check result."""
    return {
        "name": name,
        "success": bool(success),
        "observed_value": observed_value,
        "expected": expected,
        "message": message,
    }


def _non_blank(series: pd.Series) -> pd.Series:
    """Return a mask that is true for non-null, non-whitespace values."""
    return series.notna() & series.astype("string").str.strip().ne("")


def _missing_column_check(name: str, column: str, expected: str) -> dict[str, Any]:
    return _check(
        name=name,
        success=False,
        observed_value="missing_column",
        expected=expected,
        message=f"Required column '{column}' is missing.",
    )


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Validate the clean-data contract and persist a compact JSON report.

    The returned payload is deliberately stable so pipeline orchestration and
    Markdown reporting do not need to understand pandas or Great Expectations
    result objects.
    """
    if not report_name or not report_name.strip():
        raise ValueError("report_name must not be blank.")

    total_rows = int(len(df))
    missing_columns = sorted(REQUIRED_COLUMNS - set(df.columns))
    checks: list[dict[str, Any]] = [
        _check(
            name="required_columns_present",
            success=not missing_columns,
            observed_value=missing_columns,
            expected=f"columns include {sorted(REQUIRED_COLUMNS)}",
            message=(f"Missing required columns: {missing_columns}" if missing_columns else ""),
        ),
        _check(
            name="row_count_minimum",
            success=total_rows >= MIN_ROW_COUNT,
            observed_value=total_rows,
            expected=f">= {MIN_ROW_COUNT}",
            message=(
                f"Only {total_rows} rows are available; evaluation requires at least {MIN_ROW_COUNT}."
                if total_rows < MIN_ROW_COUNT
                else ""
            ),
        ),
    ]

    if "paper_id" not in df.columns:
        checks.extend(
            [
                _missing_column_check("paper_id_not_blank", "paper_id", "0 blank values"),
                _missing_column_check("paper_id_unique", "paper_id", "0 duplicate values"),
            ]
        )
    else:
        valid_ids = _non_blank(df["paper_id"])
        blank_ids = int((~valid_ids).sum())
        duplicate_ids = int(df.loc[valid_ids, "paper_id"].astype(str).duplicated().sum())
        checks.extend(
            [
                _check(
                    "paper_id_not_blank",
                    blank_ids == 0,
                    blank_ids,
                    "0 blank values",
                    f"Found {blank_ids} blank paper_id value(s)." if blank_ids else "",
                ),
                _check(
                    "paper_id_unique",
                    duplicate_ids == 0,
                    duplicate_ids,
                    "0 duplicate values",
                    f"Found {duplicate_ids} duplicate paper_id value(s)." if duplicate_ids else "",
                ),
            ]
        )

    for column, check_name in (("title", "title_not_blank"), ("summary", "summary_not_blank")):
        if column not in df.columns:
            checks.append(_missing_column_check(check_name, column, "0 blank values"))
            continue
        blank_count = int((~_non_blank(df[column])).sum())
        checks.append(
            _check(
                check_name,
                blank_count == 0,
                blank_count,
                "0 blank values",
                f"Found {blank_count} blank {column} value(s)." if blank_count else "",
            )
        )

    if "summary" not in df.columns:
        checks.append(
            _missing_column_check(
                "summary_minimum_length",
                "summary",
                f"all summaries >= {MIN_SUMMARY_CHARS} characters",
            )
        )
    else:
        summary_lengths = df["summary"].fillna("").astype(str).str.len()
        short_summaries = int((summary_lengths < MIN_SUMMARY_CHARS).sum())
        checks.append(
            _check(
                "summary_minimum_length",
                short_summaries == 0,
                short_summaries,
                f"all summaries >= {MIN_SUMMARY_CHARS} characters",
                f"Found {short_summaries} short summary value(s)." if short_summaries else "",
            )
        )

    if "summary" not in df.columns or "summary_chars" not in df.columns:
        missing = "summary" if "summary" not in df.columns else "summary_chars"
        checks.append(
            _missing_column_check(
                "summary_chars_consistent",
                missing,
                "summary_chars equals normalized summary length",
            )
        )
    else:
        expected_lengths = df["summary"].fillna("").astype(str).str.len()
        actual_lengths = pd.to_numeric(df["summary_chars"], errors="coerce")
        inconsistent = int((actual_lengths.isna() | actual_lengths.ne(expected_lengths)).sum())
        checks.append(
            _check(
                "summary_chars_consistent",
                inconsistent == 0,
                inconsistent,
                "summary_chars equals normalized summary length",
                f"Found {inconsistent} inconsistent summary_chars value(s)." if inconsistent else "",
            )
        )

    if "text_for_embedding" not in df.columns:
        checks.append(
            _missing_column_check(
                "text_for_embedding_not_blank",
                "text_for_embedding",
                "0 blank values",
            )
        )
    else:
        blank_embedding_text = int((~_non_blank(df["text_for_embedding"])).sum())
        checks.append(
            _check(
                "text_for_embedding_not_blank",
                blank_embedding_text == 0,
                blank_embedding_text,
                "0 blank values",
                (
                    f"Found {blank_embedding_text} blank text_for_embedding value(s)."
                    if blank_embedding_text
                    else ""
                ),
            )
        )

    if "published" not in df.columns:
        checks.append(
            _missing_column_check("published_parseable", "published", "all values parse as dates")
        )
    else:
        parsed_dates = pd.to_datetime(df["published"], errors="coerce", utc=True, format="mixed")
        invalid_dates = int(parsed_dates.isna().sum())
        checks.append(
            _check(
                "published_parseable",
                invalid_dates == 0,
                invalid_dates,
                "all values parse as dates",
                f"Found {invalid_dates} invalid published value(s)." if invalid_dates else "",
            )
        )

    if "age_days" not in df.columns:
        checks.extend(
            [
                _missing_column_check("age_days_valid", "age_days", "all values are numeric and >= 0"),
                _missing_column_check(
                    "age_days_within_freshness_threshold",
                    "age_days",
                    f"all values <= {settings.freshness_threshold_days}",
                ),
            ]
        )
    else:
        age_days = pd.to_numeric(df["age_days"], errors="coerce")
        invalid_age_days = int((age_days.isna() | age_days.lt(0)).sum())
        stale_rows = int(age_days.gt(settings.freshness_threshold_days).sum())
        checks.extend(
            [
                _check(
                    "age_days_valid",
                    invalid_age_days == 0,
                    invalid_age_days,
                    "all values are numeric and >= 0",
                    f"Found {invalid_age_days} invalid age_days value(s)." if invalid_age_days else "",
                ),
                _check(
                    "age_days_within_freshness_threshold",
                    stale_rows == 0,
                    stale_rows,
                    f"all values <= {settings.freshness_threshold_days}",
                    f"Found {stale_rows} stale row(s)." if stale_rows else "",
                ),
            ]
        )

    passed_checks = sum(1 for check in checks if check["success"])
    failed_checks = len(checks) - passed_checks
    file_name = f"{safe_slug(report_name).replace('-', '_')}.json"
    report_path = settings.paths.quality_dir / file_name
    payload: dict[str, Any] = {
        "report_name": report_name,
        "generated_at": now_utc().isoformat(),
        "success": failed_checks == 0,
        "total_rows": total_rows,
        "passed_checks": passed_checks,
        "failed_checks": failed_checks,
        "thresholds": {
            "minimum_rows": MIN_ROW_COUNT,
            "minimum_summary_chars": MIN_SUMMARY_CHARS,
            "freshness_threshold_days": settings.freshness_threshold_days,
        },
        "checks": checks,
        "report_path": project_relative_path(report_path, settings.paths.project_dir),
    }
    write_json(report_path, payload)
    return payload


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Summarize publication freshness and persist a JSON artifact."""
    output_path = Path(report_path)
    total_rows = int(len(df))

    if "published" in df.columns:
        published = pd.to_datetime(df["published"], errors="coerce", utc=True, format="mixed")
    else:
        published = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]")

    if "age_days" in df.columns:
        age_days = pd.to_numeric(df["age_days"], errors="coerce")
    else:
        age_days = pd.Series(float("nan"), index=df.index, dtype="float64")

    valid_published_rows = int(published.notna().sum())
    invalid_published_rows = total_rows - valid_published_rows
    invalid_age_rows = int((age_days.isna() | age_days.lt(0)).sum())
    stale_rows = int(age_days.gt(settings.freshness_threshold_days).sum())

    valid_dates = published.dropna()
    latest_published = valid_dates.max().date().isoformat() if not valid_dates.empty else None
    oldest_published = valid_dates.min().date().isoformat() if not valid_dates.empty else None

    is_fresh = (
        total_rows > 0
        and invalid_published_rows == 0
        and invalid_age_rows == 0
        and stale_rows == 0
    )
    if total_rows == 0 or valid_published_rows == 0:
        status = "unknown"
    elif invalid_published_rows or invalid_age_rows:
        status = "invalid"
    elif stale_rows:
        status = "stale"
    else:
        status = "fresh"

    payload: dict[str, Any] = {
        "generated_at": now_utc().isoformat(),
        "latest_published": latest_published,
        "oldest_published": oldest_published,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "valid_published_rows": valid_published_rows,
        "invalid_published_rows": invalid_published_rows,
        "invalid_age_rows": invalid_age_rows,
        "threshold_days": settings.freshness_threshold_days,
        "is_fresh": is_fresh,
        "status": status,
        "report_path": project_relative_path(output_path, settings.paths.project_dir),
    }
    write_json(output_path, payload)
    return payload
