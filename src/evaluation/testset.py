"""Evaluation test-set builder (Step 6 / Step 3 companion).

Generates a structured list of question/answer pairs from a clean
DataFrame, covering four question types:

    1. **summary**  — "Summarize the paper: <title>"
    2. **authors**  — "Who are the authors of <title>?"
    3. **date**     — "When was <title> published?"
    4. **categories** — "What categories does <title> belong to?"

Each item carries enough metadata (``ground_truth_doc_ids``) so that
retrieval hit-rate can be computed later.
"""

from __future__ import annotations

import hashlib
import random
from typing import Any

import pandas as pd

from core.utils import write_json

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MIN_DOCUMENTS = 3  # minimum rows to build a test set
SAMPLE_SIZE = 10   # how many papers to sample (if DataFrame is larger)
RANDOM_SEED = 42

# ---------------------------------------------------------------------------
# Question generators
# ---------------------------------------------------------------------------


def _qid(paper_id: str, qtype: str, idx: int) -> str:
    """Deterministic short hash ID for a test item."""
    raw = f"{paper_id}:{qtype}:{idx}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def _summary_question(row: dict[str, Any]) -> dict[str, Any]:
    title = row["title"]
    return {
        "question_type": "summary",
        "question": f"Summarize the paper: {title}",
        "ground_truth": row["summary"][:500],
        "ground_truth_doc_ids": [row["paper_id"]],
    }


def _authors_question(row: dict[str, Any]) -> dict[str, Any]:
    title = row["title"]
    return {
        "question_type": "authors",
        "question": f"Who are the authors of {title}?",
        "ground_truth": row["authors_joined"],
        "ground_truth_doc_ids": [row["paper_id"]],
    }


def _date_question(row: dict[str, Any]) -> dict[str, Any]:
    title = row["title"]
    pub = row.get("published", "")
    return {
        "question_type": "date",
        "question": f"When was {title} published?",
        "ground_truth": pub,
        "ground_truth_doc_ids": [row["paper_id"]],
    }


def _categories_question(row: dict[str, Any]) -> dict[str, Any]:
    title = row["title"]
    cats = row.get("categories_joined", "")
    return {
        "question_type": "categories",
        "question": f"What are the main categories of {title}?",
        "ground_truth": cats,
        "ground_truth_doc_ids": [row["paper_id]],
    }


_QUESTION_GENERATORS = [
    _summary_question,
    _authors_question,
    _date_question,
    _categories_question,
]

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Build an evaluation test-set from a cleaned DataFrame.

    Args:
        df: Clean DataFrame with columns: paper_id, title, summary,
            authors_joined, categories_joined, published.
        output_path: Where to persist the JSON test-set.

    Returns:
        List of test items, each with keys:
        ``id``, ``question_type``, ``question``, ``ground_truth``,
        ``ground_truth_doc_ids``.
    """
    if df.empty or len(df) < MIN_DOCUMENTS:
        raise ValueError(
            f"Need at least {MIN_DOCUMENTS} documents, got {len(df)}"
        )

    # Sample representative papers
    rng = random.Random(RANDOM_SEED)
    sample_n = min(SAMPLE_SIZE, len(df))
    sampled = df.sample(n=sample_n, random_state=RANDOM_SEED)

    items: list[dict[str, Any]] = []
    for idx, (_, row) in enumerate(sampled.iterrows()):
        row_dict = row.to_dict()
        gen = _QUESTION_GENERATORS[idx % len(_QUESTION_GENERATORS)]
        item = gen(row_dict)
        item["id"] = _qid(str(row_dict["paper_id"]), item["question_type"], idx)
        items.append(item)

    write_json(output_path, items)
    return items
