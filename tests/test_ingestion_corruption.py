from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest

from core.utils import read_json
from ingestion.corruption import corrupt_clean_dataframe


def _clean_dataframe() -> pd.DataFrame:
    rows = []
    for index in range(8):
        summary = f"Detailed retrieval evidence for document {index}. " * 4
        rows.append(
            {
                "paper_id": f"paper-{index}",
                "title": f"Paper {index}",
                "summary": summary,
                "authors_joined": f"Author {index}",
                "categories_joined": "Data Quality",
                "published": "2026-08-01",
                "age_days": 5.0,
                "summary_chars": len(summary),
                "text_for_embedding": f"Title: Paper {index} | Summary: {summary}",
            }
        )
    return pd.DataFrame(rows)


def test_corruption_is_logged_deterministic_and_overlaps_frozen_targets(tmp_path) -> None:
    source = _clean_dataframe()
    targets = {"paper-0", "paper-1", "paper-2", "paper-3", "paper-4", "paper-5", "paper-6", "paper-7"}
    output_log = tmp_path / "corruption_log.json"

    corrupted = corrupt_clean_dataframe(
        source,
        output_log,
        target_paper_ids=targets,
        reference_time=datetime(2026, 8, 6),
    )

    assert source.equals(_clean_dataframe())
    assert len(corrupted) == len(source) + 2
    assert corrupted["paper_id"].duplicated().sum() == 2
    assert (corrupted["summary"] == "").sum() == 2
    assert (corrupted["published"] == "2000-01-01").sum() == 2
    assert corrupted["text_for_embedding"].str.contains("Unrelated boilerplate").sum() == 2

    log = read_json(output_log)
    assert log["source_row_count"] == 8
    assert log["corrupted_row_count"] == 10
    for scenario in log["scenarios"]:
        assert scenario["changes"]
        assert {change["paper_id"] for change in scenario["changes"]} <= targets


def test_corruption_refuses_unmeasurable_target_set(tmp_path) -> None:
    with pytest.raises(ValueError, match="frozen evaluation paper IDs"):
        corrupt_clean_dataframe(
            _clean_dataframe(),
            tmp_path / "corruption_log.json",
            target_paper_ids={"not-in-dataframe"},
        )
