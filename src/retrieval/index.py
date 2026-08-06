from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb
import pandas as pd

from core.config import Settings
from core.utils import read_json, safe_slug, write_json
from retrieval.embeddings import MiniLMEmbeddings


class VectorStore:
    """ChromaDB-backed vector store using ``all-MiniLM-L6-v2``.

    Provides a simple API for ingesting a clean DataFrame, querying
    for relevant documents, and building context strings for the Agent.

    Usage::

        vs = VectorStore(settings)
        vs.ingest(clean_df)
        results = vs.query("graph neural networks", k=5)
        context = vs.get_relevant_context("What is GNN?")
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._embedder = MiniLMEmbeddings(settings.embedding_model)
        self._client = chromadb.PersistentClient(path=str(settings.paths.chroma_dir))
        self._collection = self._client.get_or_create_collection(
            name=settings.baseline_collection_name,
            configuration={"hnsw": {"space": "cosine"}},
        )

    # -- Write ---------------------------------------------------------------

    def ingest(self, dataframe: pd.DataFrame) -> int:
        """Embed and upsert all rows from *dataframe* into ChromaDB.

        Uses the ``text_for_embedding`` column as embedding source.
        Metadata columns (title, authors, categories, published, etc.)
        are stored alongside for filtering and display.

        Returns:
            Number of documents upserted.
        """
        if dataframe.empty:
            return 0

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, str | float]] = []

        for idx, row in dataframe.iterrows():
            doc_id = str(row["paper_id"])
            ids.append(doc_id)
            documents.append(str(row["text_for_embedding"]))
            metadatas.append(
                {
                    "paper_id": str(row.get("paper_id", "")),
                    "title": str(row.get("title", "")),
                    "authors_joined": str(row.get("authors_joined", "")),
                    "categories_joined": str(row.get("categories_joined", "")),
                    "published": str(row.get("published", "")),
                    "age_days": float(row.get("age_days", 0) or 0),
                    "summary": str(row.get("summary", ""))[:2000],
                }
            )

        embeddings = self._embedder.embed_documents(documents)

        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        return len(ids)

    # -- Read ----------------------------------------------------------------

    def query(self, text: str, k: int = 5) -> list[dict]:
        """Retrieve the *k* most relevant documents for *text*.

        Returns:
            List of dicts with keys: ``id``, ``score``, ``document``, ``metadata``.
        """
        if not text or not text.strip():
            return []

        query_embedding = self._embedder.embed_query(text)

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            include=["documents", "distances", "metadatas"],
        )

        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]

        hits: list[dict] = []
        for doc_id, dist, doc, meta in zip(ids, distances, documents, metadatas):
            score = round(max(0.0, 1.0 - float(dist or 0.0)), 4)
            hits.append(
                {
                    "id": doc_id,
                    "score": score,
                    "document": doc,
                    "metadata": meta,
                }
            )
        return hits

    def search(self, query: str, k: int = 5) -> list[dict]:
        """Alias for :meth:`query` — semantic search entry-point."""
        return self.query(query, k=k)

    def get_relevant_context(self, query: str, k: int = 5) -> str:
        """Build a context string from the top-*k* hits.

        Used by the Agent to ground its answers in retrieved documents.
        Each hit is formatted as a numbered reference block.
        """
        hits = self.query(query, k=k)
        if not hits:
            return "No relevant context found."

        parts: list[str] = []
        for i, hit in enumerate(hits, start=1):
            meta = hit.get("metadata", {})
            title = meta.get("title", "Untitled")
            authors = meta.get("authors_joined", "Unknown")
            score = hit.get("score", 0.0)
            doc = hit.get("document", "")
            parts.append(
                f"[{i}] {title}\n"
                f"    Authors: {authors} | Score: {score}\n"
                f"    {doc}"
            )
        return "\n\n".join(parts)

    # -- Utility -------------------------------------------------------------

    @property
    def count(self) -> int:
        """Current number of documents in the collection."""
        return self._collection.count()

    def reset(self) -> None:
        """Delete all documents and re-create the collection."""
        try:
            self._client.delete_collection(self.settings.baseline_collection_name)
        except Exception:
            pass
        self._collection = self._client.get_or_create_collection(
            name=self.settings.baseline_collection_name,
            configuration={"hnsw": {"space": "cosine"}},
        )


@dataclass(frozen=True)
class SearchResult:
    paper_id: str
    title: str
    score: float
    content: str
    metadata: dict[str, Any]


class LocalEmbeddingIndex:
    def __init__(
        self,
        settings: Settings,
        collection_name: str,
        documents: list[dict[str, Any]],
        persist_path: Path,
    ):
        self.settings = settings
        self.collection_name = collection_name
        self.documents = documents
        self.persist_path = persist_path
        self.embedding_backend = "chroma"
        self.embedding_model = MiniLMEmbeddings(settings.embedding_model)
        self.client = chromadb.PersistentClient(path=str(persist_path))
        self.collection = self.client.get_collection(name=collection_name)
        self.documents_by_paper_id = {document["paper_id"].lower(): document for document in documents}
        self.documents_by_title = {document["title"].lower(): document for document in documents}

    @staticmethod
    def _build_documents(df: pd.DataFrame) -> list[dict[str, Any]]:
        records = df.to_dict(orient="records")
        documents: list[dict[str, Any]] = []
        for index, row in enumerate(records):
            documents.append(
                {
                    "record_id": f"{row['paper_id']}::{index}",
                    "paper_id": row["paper_id"],
                    "title": row["title"],
                    "content": row["text_for_embedding"],
                    "metadata": {
                        "paper_id": row["paper_id"],
                        "title": row["title"],
                        "published": row["published"],
                        "authors_joined": row["authors_joined"],
                        "categories_joined": row["categories_joined"],
                        "summary": row["summary"],
                        "abs_url": row["abs_url"],
                        "pdf_url": row["pdf_url"],
                    },
                }
            )
        return documents

    @staticmethod
    def _derive_collection_name(settings: Settings, embeddings_output_path: Path | None) -> str:
        if embeddings_output_path is None:
            return settings.baseline_collection_name

        name_map = {
            settings.paths.embeddings_json.resolve(): settings.baseline_collection_name,
            settings.paths.corrupted_embeddings_json.resolve(): settings.corrupted_collection_name,
            settings.paths.repaired_embeddings_json.resolve(): settings.repaired_collection_name,
        }
        resolved_path = embeddings_output_path.resolve()
        if resolved_path in name_map:
            return name_map[resolved_path]
        return safe_slug(embeddings_output_path.stem)

    @classmethod
    def build(
        cls,
        df: pd.DataFrame,
        settings: Settings,
        embeddings_output_path: Path | None = None,
    ) -> "LocalEmbeddingIndex":
        collection_name = cls._derive_collection_name(settings, embeddings_output_path)
        documents = cls._build_documents(df)
        persist_path = settings.paths.chroma_dir
        persist_path.mkdir(parents=True, exist_ok=True)

        embedding_model = MiniLMEmbeddings(settings.embedding_model)
        client = chromadb.PersistentClient(path=str(persist_path))
        try:
            client.delete_collection(name=collection_name)
        except Exception:
            pass
        collection = client.create_collection(
            name=collection_name,
            configuration={"hnsw": {"space": "cosine"}},
        )
        embeddings = embedding_model.embed_documents([document["content"] for document in documents])
        collection.add(
            ids=[document["record_id"] for document in documents],
            embeddings=embeddings,
            documents=[document["content"] for document in documents],
            metadatas=[document["metadata"] for document in documents],
        )

        manifest_path = embeddings_output_path or settings.paths.embeddings_json
        write_json(
            manifest_path,
            {
                "backend": "chroma",
                "embedding_model": settings.embedding_model,
                "persist_path": str(persist_path),
                "collection_name": collection_name,
                "documents": documents,
            },
        )
        return cls(
            settings=settings,
            collection_name=collection_name,
            documents=documents,
            persist_path=persist_path,
        )

    @classmethod
    def load(cls, settings: Settings, embeddings_path: Path | None = None) -> "LocalEmbeddingIndex":
        payload = read_json(embeddings_path or settings.paths.embeddings_json)
        return cls(
            settings=settings,
            collection_name=payload["collection_name"],
            documents=payload["documents"],
            persist_path=Path(payload["persist_path"]),
        )

    def search(self, query: str, top_k: int | None = None) -> list[SearchResult]:
        query_embedding = self.embedding_model.embed_query(query)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k or self.settings.top_k,
            include=["documents", "metadatas", "distances"],
        )
        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        scored: list[SearchResult] = []
        for record_id, content, metadata, distance in zip(ids, documents, metadatas, distances, strict=False):
            if not record_id or not metadata or not content:
                continue
            scored.append(
                SearchResult(
                    paper_id=str(metadata["paper_id"]),
                    title=str(metadata["title"]),
                    score=max(0.0, 1.0 - float(distance or 0.0)),
                    content=str(content),
                    metadata=dict(metadata),
                )
            )
        return scored

    def lookup(self, value: str) -> dict[str, Any] | None:
        needle = value.strip().lower()
        if needle in self.documents_by_paper_id:
            return self.documents_by_paper_id[needle]
        if needle in self.documents_by_title:
            return self.documents_by_title[needle]
        return None
