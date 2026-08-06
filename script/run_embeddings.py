"""Step 6 — Embedding & Vector Store (ChromaDB + MiniLM).

Creates embeddings using ``sentence-transformers/all-MiniLM-L6-v2`` and
ingests them into a ChromaDB collection with cosine similarity.

Usage::

    cd K4-Day10-2A202601050-DangVanNhan
    python -m script.run_embeddings          # full pipeline
    python -m script.run_embeddings --query "graph neural networks"  # custom query

This script:
  1. Loads raw Crossref records from ``data/raw/crossref_records.json``
  2. Cleans & models data (``text_for_embedding`` column)
  3. Saves clean artifacts (CSV + JSON) to ``data/clean/``
  4. Embeds all documents with MiniLM-L6-v2
  5. Ingests into ChromaDB (``data/chroma/``)
  6. Runs sample retrieval queries and prints results
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

# Fix Windows cp1252 console encoding for Unicode titles
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Ensure src/ is on sys.path ──────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_DIR = _PROJECT_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from core.config import load_settings
from core.utils import read_json, write_json
from ingestion.cleaning import build_clean_dataframe, validate_clean_dataframe
from ingestion.crossref import PaperRecord
from retrieval.embeddings import MiniLMEmbeddings
from retrieval.index import LocalEmbeddingIndex, VectorStore


# ── Sample queries for retrieval testing ────────────────────────────────────

SAMPLE_QUERIES = [
    "What are the latest advances in retrieval augmented generation?",
    "graph neural networks for drug discovery",
    "Who is working on reinforcement learning?",
    "attention mechanisms in transformer models",
    "RAG pipelines for large language models",
]


def _load_raw_records(settings) -> list[PaperRecord]:
    """Load raw Crossref records from JSON snapshot."""
    raw_path = settings.paths.raw_records_json
    if not raw_path.exists():
        raise FileNotFoundError(
            f"Raw records not found: {raw_path}\n"
            "Run the ingestion step first (fetch_source_records)."
        )
    data = read_json(raw_path)
    records = [PaperRecord(**item) for item in data]
    print(f"  Loaded {len(records)} raw records from {raw_path.name}")
    return records


def _clean_and_save(records: list[PaperRecord], settings) -> pd.DataFrame:
    """Clean raw records and save as CSV + JSON."""
    run_date = datetime.now()
    print(f"  Cleaning {len(records)} records...")
    clean_df = build_clean_dataframe(records, run_date)
    print(f"  > {len(clean_df)} clean documents after dedup & validation")

    # Save CSV
    csv_path = settings.paths.clean_csv
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    clean_df.to_csv(csv_path, index=False)
    print(f"  > Saved: {csv_path}")

    # Save JSON
    json_path = settings.paths.clean_json
    write_json(json_path, clean_df.to_dict(orient="records"))
    print(f"  > Saved: {json_path}")

    return clean_df


def _build_vector_store(clean_df: pd.DataFrame, settings) -> VectorStore:
    """Create embeddings and ingest into ChromaDB via VectorStore."""
    print(f"  Embedding model: {settings.embedding_model}")
    print(f"  ChromaDB dir:    {settings.paths.chroma_dir}")

    vs = VectorStore(settings)
    vs.reset()  # start fresh

    print(f"  Ingesting {len(clean_df)} documents into ChromaDB...")
    t0 = time.time()
    count = vs.ingest(clean_df)
    elapsed = time.time() - t0
    print(f"  > Ingested {count} documents in {elapsed:.2f}s")
    print(f"  > Collection count: {vs.count}")

    return vs


def _build_local_index(clean_df: pd.DataFrame, settings) -> LocalEmbeddingIndex:
    """Build LocalEmbeddingIndex for evaluation and QA."""
    index = LocalEmbeddingIndex.build(
        df=clean_df,
        settings=settings,
        embeddings_output_path=settings.paths.embeddings_json,
    )
    print(f"  > LocalEmbeddingIndex built: {index.collection_name} ({index.collection.count()} docs)")
    return index


def _run_retrieval_demo(vs: VectorStore, queries: list[str], top_k: int = 4) -> None:
    """Run sample queries and display retrieval results."""
    print("\n" + "=" * 72)
    print("RETRIEVAL DEMO — ChromaDB + MiniLM-L6-v2")
    print("=" * 72)

    for i, query in enumerate(queries, 1):
        print(f"\n{'-' * 72}")
        print(f"Query {i}: {query}")
        print(f"{'-' * 72}")

        t0 = time.time()
        hits = vs.query(query, k=top_k)
        elapsed = (time.time() - t0) * 1000

        if not hits:
            print("  (no results)")
            continue

        print(f"  Found {len(hits)} results in {elapsed:.1f}ms:\n")
        for j, hit in enumerate(hits, 1):
            meta = hit["metadata"]
            score = hit["score"]
            title = meta.get("title", "Untitled")
            authors = meta.get("authors_joined", "Unknown")[:60]
            print(f"  [{j}] score={score:.4f}  {title}")
            print(f"      authors: {authors}")

        # Show context string for first query
        if i == 1:
            print(f"\n  -- Context string (first query) --")
            context = vs.get_relevant_context(query, k=top_k)
            # Print first 500 chars
            print(context[:500])
            if len(context) > 500:
                print("  ... (truncated)")


def _save_retrieval_results(vs: VectorStore, queries: list[str], settings) -> None:
    """Save retrieval results for inspection."""
    results = {}
    for query in queries:
        hits = vs.query(query, k=settings.top_k)
        results[query] = [
            {
                "rank": j,
                "paper_id": hit["id"],
                "title": hit["metadata"].get("title", ""),
                "score": hit["score"],
            }
            for j, hit in enumerate(hits, 1)
        ]

    out_path = settings.paths.embeddings_json.parent / "retrieval_sample_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(out_path, results)
    print(f"\n  > Sample retrieval results saved: {out_path}")


def main() -> None:
    settings = load_settings()
    t_start = time.time()

    print("=" * 72)
    print("STEP 6 — Embedding & Vector Store (ChromaDB + MiniLM-L6-v2)")
    print("=" * 72)

    # ── 1. Load raw records ─────────────────────────────────────────────────
    print("\n[1/6] Loading raw records...")
    records = _load_raw_records(settings)

    # ── 2. Clean & save ─────────────────────────────────────────────────────
    print("\n[2/6] Cleaning & modeling data...")
    clean_df = _clean_and_save(records, settings)

    # ── 3. Build LocalEmbeddingIndex (creates ChromaDB collection) ──────────
    print("\n[3/6] Building LocalEmbeddingIndex (for eval/QA)...")
    index = _build_local_index(clean_df, settings)

    # ── 4. Create VectorStore (reuses the same collection) ──────────────────
    print("\n[4/6] Creating VectorStore wrapper...")
    vs = VectorStore(settings)
    print(f"  > VectorStore ready, collection count: {vs.count}")

    # ── 5. Retrieval demo ───────────────────────────────────────────────────
    print("\n[5/6] Running retrieval demo...")
    _run_retrieval_demo(vs, SAMPLE_QUERIES, top_k=settings.top_k)

    # ── 6. Save results ─────────────────────────────────────────────────────
    print("\n[6/6] Saving retrieval sample results...")
    _save_retrieval_results(vs, SAMPLE_QUERIES, settings)

    # ── Summary ─────────────────────────────────────────────────────────────
    elapsed = time.time() - t_start
    print("\n" + "=" * 72)
    print("DONE")
    print(f"  Documents embedded: {vs.count}")
    print(f"  Collection:         {settings.baseline_collection_name}")
    print(f"  Embedding model:    {settings.embedding_model}")
    print(f"  ChromaDB dir:       {settings.paths.chroma_dir}")
    print(f"  Total time:         {elapsed:.2f}s")
    print("=" * 72)


if __name__ == "__main__":
    main()
