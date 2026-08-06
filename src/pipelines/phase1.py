"""Baseline RAG pipeline — end-to-end orchestration.

Follows the 10-step Guide (Steps 1-10).

Usage::

    python -m pipelines.phase1
    python scripts/run_phase1.py            # convenience wrapper
    PHASE1_STEPS=fetch,clean python -m pipelines.phase1   # selective
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from core.config import Settings, load_settings
from core.utils import write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import PaperRecord, fetch_source_records
from observability.quality import run_data_quality_checks, build_freshness_report
from retrieval.embeddings import MiniLMEmbeddings
from retrieval.index import LocalEmbeddingIndex, VectorStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STEPS = [
    "fetch",
    "clean",
    "save_clean",
    "embeddings_init",
    "build_index",
    "testset",
    "evaluate",
    "quality",
    "report",
    "demo",
]


def _selected_steps() -> set[str]:
    env = os.getenv("PHASE1_STEPS", "")
    if not env:
        return set(STEPS)
    return {s.strip() for s in env.split(",") if s.strip()}


def _save_clean_artifacts(df: pd.DataFrame, settings: Settings) -> None:
    """Persist cleaned DataFrame as CSV + JSON."""
    df.to_csv(settings.paths.clean_csv, index=False)
    write_json(settings.paths.clean_json, df.to_dict(orient="records"))
    print(f"  → Saved: {settings.paths.clean_csv}")
    print(f"  → Saved: {settings.paths.clean_json}")


def _generate_report(
    *,
    settings: Settings,
    clean_df: pd.DataFrame,
    index_count: int,
    quality_report: dict,
    report_path: Path,
) -> None:
    """Write a Markdown summary of the pipeline run."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# Phase 1 — Baseline RAG Report",
        f"_Generated: {now}_",
        "",
        "## 1. Data Ingestion",
        f"- Clean documents: **{len(clean_df)}**",
        f"- Categories observed: {clean_df['categories_joined'].nunique()}",
        "",
        "## 2. Embedding & Index",
        f"- Model: `{settings.embedding_model}`",
        f"- Documents indexed: **{index_count}**",
        "",
        "## 3. Quality Checks",
    ]
    for key, val in quality_report.items():
        lines.append(f"- **{key}**: {val}")
    lines.append("")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def main() -> None:
    settings = load_settings()
    steps = _selected_steps()
    run_start = time.time()

    # ── Step 1: Load settings ─────────────────────────────────────────────
    print("[Step 1] Settings loaded.")

    # ── Step 2: Fetch raw records ──────────────────────────────────────────
    records: list[PaperRecord] = []

    if "fetch" in steps:
        print("[Step 2] Fetching papers from Crossref…")
        records = fetch_source_records(settings)
        print(f"  → Fetched {len(records)} records.")
    else:
        # Load from disk if skipping fetch
        from core.utils import read_json

        payload = read_json(settings.paths.raw_records_json)
        records = [PaperRecord(**r) for r in payload]
        print(f"[Step 2] Loaded {len(records)} raw records from disk.")

    # ── Step 3: Clean & model ─────────────────────────────────────────────
    run_date = datetime.now()
    clean_df = pd.DataFrame()

    if "clean" in steps:
        print("[Step 3] Cleaning data…")
        clean_df = build_clean_dataframe(records, run_date)
        print(f"  → Clean documents: {len(clean_df)}")

    # ── Step 4: Save clean artifacts ───────────────────────────────────────
    if "save_clean" in steps and not clean_df.empty:
        print("[Step 4] Saving clean CSV/JSON…")
        _save_clean_artifacts(clean_df, settings)

    # ── Step 5: Initialize embeddings & build index ───────────────────────
    embeddings = MiniLMEmbeddings(settings.embedding_model)
    index = None

    if "embeddings_init" in steps:
        print(f"[Step 5a] Embeddings model: {settings.embedding_model}")

    if "build_index" in steps and not clean_df.empty:
        print("[Step 5b] Building ChromaDB index…")
        index = LocalEmbeddingIndex.build(df=clean_df, settings=settings)
        print(f"  → Indexed {index.count} documents.")

        # Also demonstrate the new VectorStore API
        vs = VectorStore(settings)
        vs.ingest(clean_df)
        print(f"  → VectorStore ingested {vs.count} documents.")

    # ── Step 6: Evaluation test-set ───────────────────────────────────────
    test_set_path = settings.paths.eval_testset

    if "testset" in steps and not clean_df.empty:
        print("[Step 6] Building evaluation test-set…")
        test_set = build_test_set(clean_df, test_set_path)
        print(f"  → {len(test_set)} test items.")

    # ── Step 7: Evaluate ──────────────────────────────────────────────────
    if "evaluate" in steps and index is not None:
        print("[Step 7] Running evaluation…")
        bundle = evaluate_pipeline(
            settings=settings,
            index=index,
            test_set_path=test_set_path,
            metrics_output_path=settings.paths.baseline_metrics,
            answers_output_path=settings.paths.baseline_answers,
        )
        print(f"  → Retrieval hit-rate: {bundle.summary['retrieval_hit_rate']:.2%}")

    # ── Step 8: Quality checks ────────────────────────────────────────────
    quality_report: dict = {}

    if "quality" in steps and not clean_df.empty:
        print("[Step 8] Running quality & freshness checks…")
        try:
            quality_report = run_data_quality_checks(
                df=clean_df,
                settings=settings,
                report_name="baseline",
            )
            print(f"  → Quality checks: {quality_report}")
        except NotImplementedError:
            print("  ⚠ Quality checks not yet implemented — skipping.")
            quality_report = {"status": "skipped (not implemented)"}

    # ── Step 9: Markdown report ────────────────────────────────────────────
    if "report" in steps:
        print("[Step 9] Generating Markdown report…")
        _generate_report(
            settings=settings,
            clean_df=clean_df,
            index_count=index.count if index else 0,
            quality_report=quality_report,
            report_path=settings.paths.baseline_report,
        )

    # ── Step 10: Agent demo ───────────────────────────────────────────────
    if "demo" in steps and index is not None:
        print("[Step 10] Agent demo (sample questions)…")
        from retrieval.qa import answer_question

        demo_questions = [
            "What are the latest advances in graph neural networks?",
            "Who is working on reinforcement learning?",
            "What papers discuss attention mechanisms?",
        ]
        for q in demo_questions:
            result = answer_question(q, settings=settings, index=index)
            print(f"\n  Q: {q}")
            print(f"  A: {result.answer[:200]}…")

    elapsed = time.time() - run_start
    print(f"\n✅ Pipeline complete in {elapsed:.1f}s — {len(steps)} steps executed.")


if __name__ == "__main__":
    main()
