from __future__ import annotations

from typing import Any

from langchain.agents import create_agent
from langchain.tools import tool

from core.config import Settings
from retrieval.index import LocalEmbeddingIndex, SearchResult
from retrieval.llm import build_llm


def _format_tool_evidence(result: SearchResult) -> str:
    """Expose the factual metadata that an agent needs to answer corpus questions."""
    published = str(result.metadata.get("published") or "unknown")
    return (
        f"paper_id: {result.paper_id}\n"
        f"title: {result.title}\n"
        f"published: {published}\n"
        f"score: {result.score:.4f}\n"
        f"{result.content}"
    )


def build_agent(
    settings: Settings,
    index: LocalEmbeddingIndex,
    retrieval_trace: list[SearchResult] | None = None,
):
    """Build an LLM agent and optionally expose its tool retrieval trace.

    ``retrieval_trace`` is intentionally caller-owned so evaluation can reset
    it for every question and persist exactly the documents the agent used.
    """
    trace = retrieval_trace if retrieval_trace is not None else []

    @tool
    def semantic_search_papers(query: str, top_k: int = 4) -> str:
        """Search the local paper corpus with embeddings and return the most relevant papers."""
        results = index.search(query, top_k=top_k)
        trace.extend(results)
        return "\n\n".join(_format_tool_evidence(result) for result in results)

    @tool
    def lookup_paper(paper_id_or_title: str) -> str:
        """Look up a paper by exact paper_id or exact title from the local corpus."""
        record = index.lookup(paper_id_or_title)
        if not record:
            return "No exact paper match found."
        found_result = SearchResult(
            paper_id=str(record["paper_id"]),
            title=str(record["title"]),
            score=1.0,
            content=str(record["content"]),
            metadata=dict(record["metadata"]),
        )
        trace.append(found_result)
        return _format_tool_evidence(found_result)

    llm = build_llm(settings=settings, temperature=0.0)
    return create_agent(
        model=llm,
        tools=[semantic_search_papers, lookup_paper],
        system_prompt=(
            "You answer questions about the indexed scholarly paper corpus sourced from Crossref. "
            "Use tools before answering factual questions. "
            "If the indexed corpus does not support the answer, say so clearly."
        ),
        name="paper_corpus_agent",
    )


def _content_to_text(content: Any) -> str:
    """Normalize LangChain provider content blocks into plain answer text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
            else:
                text = getattr(block, "text", None)
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(part for part in parts if part.strip())
    return str(content)


def run_agent_question(agent: Any, question: str) -> str:
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    messages = result.get("messages", [])
    if not messages:
        return ""
    final_message = messages[-1]
    return _content_to_text(getattr(final_message, "content", final_message))
