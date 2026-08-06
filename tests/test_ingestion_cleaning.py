from __future__ import annotations

from datetime import datetime

from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import PaperRecord


def _record(*, paper_id: str, title: str, summary: str, published: str) -> PaperRecord:
    return PaperRecord(
        paper_id=paper_id,
        title=title,
        summary=summary,
        authors=["Ada Lovelace", "Grace Hopper"],
        categories=["Machine Learning"],
        primary_category="Machine Learning",
        published=published,
        updated=published,
        abs_url="https://doi.org/example",
        pdf_url="",
        comment="",
    )


def test_cleaning_enforces_summary_date_and_embedding_contract() -> None:
    valid_summary = "<jats:p>" + ("A detailed scholarly finding. " * 5) + "</jats:p>"
    records = [
        _record(
            paper_id="valid",
            title="<b>Valid paper</b>",
            summary=valid_summary,
            published="2026-08-01",
        ),
        _record(
            paper_id="short",
            title="Short paper",
            summary="Too short.",
            published="2026-08-01",
        ),
    ]

    dataframe = build_clean_dataframe(records, datetime(2026, 8, 6))

    assert dataframe["paper_id"].tolist() == ["valid"]
    row = dataframe.iloc[0]
    assert row["title"] == "Valid paper"
    assert "<" not in row["summary"]
    assert row["published"] == "2026-08-01"
    assert row["age_days"] == 5.0
    assert row["text_for_embedding"].startswith(
        "Title: Valid paper | Authors: Ada Lovelace, Grace Hopper | Summary:"
    )
