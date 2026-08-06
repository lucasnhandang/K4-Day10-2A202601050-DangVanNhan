from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

import pandas as pd

from core.utils import write_json
from ingestion.cleaning import _build_text_for_embedding


_REQUIRED_COLUMNS = {
    "paper_id",
    "title",
    "summary",
    "authors_joined",
    "categories_joined",
    "published",
    "age_days",
    "summary_chars",
    "text_for_embedding",
}
_STALE_DATE = "2000-01-01"
_NOISE = " ".join(
    [
        "Unrelated boilerplate about cafeteria menus, weather forecasts, and office supplies."
        " This injected text is intentionally unrelated to scholarly retrieval.",
    ]
    * 30
)


def _target_ids_in_dataframe(df: pd.DataFrame, target_paper_ids: Iterable[str] | None) -> list[str]:
    """Return deterministic, frozen-set target IDs that are present in *df*."""
    if target_paper_ids is None:
        raise ValueError("target_paper_ids is required to prove frozen-test-set overlap.")

    available = {str(value) for value in df["paper_id"].tolist()}
    targets = sorted({str(value) for value in target_paper_ids if str(value).strip()} & available)
    if not targets:
        raise ValueError(
            "None of the frozen evaluation paper IDs exist in the clean dataframe; "
            "refusing to create an unmeasurable corruption run."
        )
    return targets


def _scenario_targets(target_ids: list[str], offset: int, count: int = 2) -> list[str]:
    """Cycle through target IDs so every scenario overlaps the frozen set."""
    return [target_ids[(offset + index) % len(target_ids)] for index in range(count)]


def _row_snapshot(row: pd.Series) -> dict[str, object]:
    """Keep the log compact while recording every field relevant to corruption."""
    return {
        "summary_chars": int(row["summary_chars"]),
        "published": str(row["published"]),
        "age_days": float(row["age_days"]),
        "text_for_embedding_chars": len(str(row["text_for_embedding"])),
    }


def _rebuild_embedding_text(row: pd.Series) -> str:
    return _build_text_for_embedding(
        title=str(row["title"]),
        summary=str(row["summary"]),
        authors_joined=str(row["authors_joined"]),
        categories_joined=str(row["categories_joined"]),
        skills=[],
    )


def corrupt_clean_dataframe(
    df: pd.DataFrame,
    output_log_path: Path,
    *,
    target_paper_ids: Iterable[str] | None = None,
    reference_time: datetime | None = None,
) -> pd.DataFrame:
    """Create deterministic corruption that is measurable against a frozen test set.

    The caller supplies IDs referenced by the frozen evaluation artifact.  Each
    scenario deliberately modifies at least one of those documents; otherwise
    a data-corruption experiment could appear healthy merely because its test
    questions never touch the damaged records.
    """
    missing_columns = sorted(_REQUIRED_COLUMNS - set(df.columns))
    if missing_columns:
        raise ValueError(f"Cannot corrupt dataframe missing columns: {missing_columns}")
    if df.empty:
        raise ValueError("Cannot corrupt an empty dataframe.")

    corrupted = df.copy(deep=True).reset_index(drop=True)
    target_ids = _target_ids_in_dataframe(corrupted, target_paper_ids)
    now = reference_time or datetime.now()
    now = now.replace(tzinfo=None) if now.tzinfo is not None else now
    stale_age_days = float((now.date() - pd.Timestamp(_STALE_DATE).date()).days)

    scenario_ids = {
        "blank_summary": _scenario_targets(target_ids, offset=0),
        "stale_date": _scenario_targets(target_ids, offset=2),
        "add_noise": _scenario_targets(target_ids, offset=4),
        "duplicates": _scenario_targets(target_ids, offset=6),
    }
    scenarios: list[dict[str, object]] = []

    blank_changes: list[dict[str, object]] = []
    for paper_id in scenario_ids["blank_summary"]:
        row_index = int(corrupted.index[corrupted["paper_id"].astype(str) == paper_id][0])
        before = _row_snapshot(corrupted.loc[row_index])
        corrupted.loc[row_index, "summary"] = ""
        corrupted.loc[row_index, "summary_chars"] = 0
        corrupted.loc[row_index, "extracted_skills"] = "[]"
        corrupted.loc[row_index, "text_for_embedding"] = _rebuild_embedding_text(corrupted.loc[row_index])
        blank_changes.append(
            {
                "paper_id": paper_id,
                "row_index": row_index,
                "before": before,
                "after": _row_snapshot(corrupted.loc[row_index]),
            }
        )
    scenarios.append({"name": "blank_summary", "changes": blank_changes})

    stale_changes: list[dict[str, object]] = []
    for paper_id in scenario_ids["stale_date"]:
        row_index = int(corrupted.index[corrupted["paper_id"].astype(str) == paper_id][0])
        before = _row_snapshot(corrupted.loc[row_index])
        corrupted.loc[row_index, "published"] = _STALE_DATE
        corrupted.loc[row_index, "age_days"] = stale_age_days
        stale_changes.append(
            {
                "paper_id": paper_id,
                "row_index": row_index,
                "before": before,
                "after": _row_snapshot(corrupted.loc[row_index]),
            }
        )
    scenarios.append({"name": "stale_date", "changes": stale_changes})

    noise_changes: list[dict[str, object]] = []
    for paper_id in scenario_ids["add_noise"]:
        row_index = int(corrupted.index[corrupted["paper_id"].astype(str) == paper_id][0])
        before = _row_snapshot(corrupted.loc[row_index])
        corrupted.loc[row_index, "text_for_embedding"] = (
            f"{_NOISE}\n\n{corrupted.loc[row_index, 'text_for_embedding']}"
        )
        noise_changes.append(
            {
                "paper_id": paper_id,
                "row_index": row_index,
                "before": before,
                "after": _row_snapshot(corrupted.loc[row_index]),
            }
        )
    scenarios.append({"name": "add_noise", "changes": noise_changes})

    duplicate_rows: list[dict[str, object]] = []
    for paper_id in scenario_ids["duplicates"]:
        source_index = int(corrupted.index[corrupted["paper_id"].astype(str) == paper_id][0])
        duplicate_rows.append(
            {
                "paper_id": paper_id,
                "source_row_index": source_index,
                "duplicate_row_index": len(corrupted) + len(duplicate_rows),
                "copied_fields": sorted(corrupted.columns.tolist()),
            }
        )
    duplicate_frame = corrupted.loc[
        [entry["source_row_index"] for entry in duplicate_rows]
    ].copy()
    corrupted = pd.concat([corrupted, duplicate_frame], ignore_index=True)
    scenarios.append({"name": "duplicates", "changes": duplicate_rows})

    log = {
        "schema_version": 1,
        "reference_time": now.isoformat(),
        "source_row_count": int(len(df)),
        "corrupted_row_count": int(len(corrupted)),
        "frozen_target_paper_ids_present": target_ids,
        "scenarios": scenarios,
    }
    write_json(Path(output_log_path), log)
    return corrupted
