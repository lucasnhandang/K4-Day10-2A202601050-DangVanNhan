"""Data cleaning & modelling pipeline (Step 3).

Provides:
    - ``build_clean_dataframe``  : raw PaperRecords → clean DataFrame
    - helper columns ready for embedding (``text_for_embedding``)

The DataFrame follows the schema defined in ``core.config.PIPELINE_CONFIG``
and is the single source-of-truth consumed by the Vector Store.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

from ingestion.crossref import PaperRecord

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Text normalisation helpers
# ---------------------------------------------------------------------------

_WHITESPACE = re.compile(r"\s+")


def _norm_text(text: str | None) -> str:
    """Collapse internal whitespace and strip."""
    if not text:
        return ""
    return _WHITESPACE.sub(" ", text).strip()


def _parse_datetime(raw: str | None) -> datetime | None:
    """Best-effort parse of ISO-8601 or ``YYYY-MM`` strings."""
    if not raw:
        return None
    raw = raw.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%Y-%m"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Skill taxonomy (loaded from YAML config)
# ---------------------------------------------------------------------------

_TAXONOMY_PATH = Path(__file__).resolve().parent.parent / "core" / "skill_taxonomy.yaml"


def _load_taxonomy() -> dict[str, list[str]]:
    """Load skill taxonomy từ YAML config file.

    Returns empty dict nếu file không tồn tại — pipeline vẫn chạy được.
    """
    if not _TAXONOMY_PATH.exists():
        logger.warning("Skill taxonomy not found at %s, using empty taxonomy", _TAXONOMY_PATH)
        return {}
    with open(_TAXONOMY_PATH, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data.get("domains", {})


_SKILL_TAXONOMY: dict[str, list[str]] = _load_taxonomy()


def _extract_skills(text: str) -> list[str]:
    """Extract domain skills bằng cách match text với taxonomy config.

    Skills được load từ ``core/skill_taxonomy.yaml`` — thêm/sửa skill
    chỉ cần edit file YAML, không cần chạm code.
    """
    if not text:
        return []
    lower = text.lower()
    found: set[str] = set()
    for _domain, keywords in _SKILL_TAXONOMY.items():
        for kw in keywords:
            if kw in lower:
                found.add(kw)
    return sorted(found)


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

# Các columns bắt buộc cho downstream consumption (VectorStore, LocalEmbeddingIndex)
REQUIRED_COLUMNS = [
    "paper_id",
    "title",
    "summary",
    "text_for_embedding",
    "authors_joined",
    "categories_joined",
    "published",
    "age_days",
]

# Các columns không được phép có null
NULL_UNSAFE_COLUMNS = ["paper_id", "title", "summary", "text_for_embedding"]


def validate_clean_dataframe(df: pd.DataFrame) -> None:
    """Assert clean DataFrame có đủ columns và không có null ở critical fields.

    Gọi sau ``build_clean_dataframe`` để đảm bảo output đủ chuẩn
    cho downstream consumers (VectorStore, LocalEmbeddingIndex).

    Raises:
        ValueError: nếu thiếu columns hoặc có null ở critical fields.
    """
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Clean DataFrame missing required columns: {missing}")

    for col in NULL_UNSAFE_COLUMNS:
        null_count = int(df[col].isna().sum())
        if null_count > 0:
            raise ValueError(
                f"Clean DataFrame has {null_count} null value(s) "
                f"in required column '{col}'"
            )


# ---------------------------------------------------------------------------
# Core public API
# ---------------------------------------------------------------------------

def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Transform raw ``PaperRecord`` objects into a clean, embed-ready DataFrame.

    Steps:
        1. Normalize title, summary, authors, categories.
        2. Parse *published* / *updated* date strings.
        3. Compute ``age_days`` (days since publication).
        4. Build helper columns: ``authors_joined``, ``categories_joined``,
           ``summary_chars``, ``extracted_skills``, ``text_for_embedding``.
        5. Deduplicate by ``paper_id``.
        6. Drop rows with empty summary or title.
        7. Sort by ``age_days`` ascending (most recent first).

    Returns:
        pd.DataFrame with one row per unique paper.
    """
    if not records:
        return pd.DataFrame()

    rows: list[dict] = []
    for rec in records:
        # -- 1. Normalize text fields --
        title = _norm_text(rec.title)
        summary = _norm_text(rec.summary)
        authors_list = [_norm_text(a) for a in (rec.authors or [])]
        categories = list(rec.categories or [])

        # -- 2. Parse dates --
        published_dt = _parse_datetime(rec.published)

        # -- 3. age_days --
        age_days: float | None = None
        if published_dt is not None:
            age_days = (run_date - published_dt).total_seconds() / 86_400

        # -- 4. Helper columns --
        authors_joined = ", ".join(authors_list)
        categories_joined = ", ".join(categories)
        summary_chars = len(summary)
        extracted_skills = _extract_skills(f"{title} {summary}")

        # -- 5. text_for_embedding --
        text_for_embedding = _build_text_for_embedding(
            title=title,
            summary=summary,
            authors_joined=authors_joined,
            categories_joined=categories_joined,
            skills=extracted_skills,
        )

        rows.append(
            {
                "paper_id": rec.paper_id,
                "doi": rec.abs_url.removeprefix("https://doi.org/") if rec.abs_url else "",
                "title": title,
                "summary": summary,
                "authors": authors_list,
                "authors_joined": authors_joined,
                "categories": categories,
                "categories_joined": categories_joined,
                "published": published_dt.isoformat() if published_dt else "",
                "updated": rec.updated or "",
                "abs_url": rec.abs_url or "",
                "pdf_url": rec.pdf_url or "",
                "age_days": age_days,
                "summary_chars": summary_chars,
                "extracted_skills": extracted_skills,
                "text_for_embedding": text_for_embedding,
                "source": "Crossref REST API",
            }
        )

    df = pd.DataFrame(rows)

    # -- 5. Deduplicate --
    df.drop_duplicates(subset=["paper_id"], inplace=True)

    # -- 6. Drop rows missing essential content --
    df = df[df["summary"].astype(bool) & df["title"].astype(bool)].copy()

    # -- 7. Sort ascending age_days (newest first); NaN last --
    df.sort_values("age_days", na_position="last", inplace=True)
    df.reset_index(drop=True, inplace=True)

    # -- 8. Validate schema before returning --
    validate_clean_dataframe(df)

    return df


def _build_text_for_embedding(
    *,
    title: str,
    summary: str,
    authors_joined: str,
    categories_joined: str,
    skills: list[str],
) -> str:
    """Compose a single string optimised for sentence-transformer embedding.

    Structure:
        ``[TITLE] summary [CATEGORIES] skills``

    The title is repeated once explicitly; authors are intentionally
    **excluded** from embedding text to avoid query/bias mismatch —
    they are stored separately for display.
    """
    parts: list[str] = []
    if title:
        parts.append(f"Title: {title}")
    if summary:
        # Truncate very long summaries to keep embedding vector focused
        truncated = summary[:1500]
        parts.append(f"Summary: {truncated}")
    if categories_joined:
        parts.append(f"Categories: {categories_joined}")
    if skills:
        parts.append(f"Skills: {', '.join(skills)}")
    return " | ".join(parts)
