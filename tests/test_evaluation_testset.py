from __future__ import annotations

import math

import pandas as pd

from core.utils import read_json
from evaluation.testset import build_test_set


def test_skips_question_types_with_blank_ground_truth(tmp_path) -> None:
    dataframe = pd.DataFrame(
        [
            {
                "paper_id": f"paper-{index}",
                "title": f"Paper {index}",
                "summary": "A non-empty summary suitable for evaluation.",
                "authors_joined": f"Author {index}",
                "published": "2026-08-01",
                "categories_joined": "" if index != 2 else math.nan,
            }
            for index in range(1, 5)
        ]
    )
    output_path = tmp_path / "test_set.json"

    items = build_test_set(dataframe, output_path)

    assert len(items) == 4
    assert all(item["question_type"] != "categories" for item in items)
    assert all(isinstance(item["ground_truth"], str) and item["ground_truth"] for item in items)
    assert read_json(output_path) == items
