from __future__ import annotations

from types import SimpleNamespace

from retrieval.agent import _format_tool_evidence, run_agent_question
from retrieval.index import SearchResult


class _FakeAgent:
    def invoke(self, _payload):
        return {
            "messages": [
                SimpleNamespace(content=[{"type": "text", "text": "Grounded agent answer."}])
            ]
        }


def test_run_agent_question_normalizes_provider_content_blocks() -> None:
    assert run_agent_question(_FakeAgent(), "Question") == "Grounded agent answer."


def test_tool_evidence_includes_published_metadata() -> None:
    result = SearchResult(
        paper_id="safe-rag",
        title="SafeRAG",
        score=0.91,
        content="Title: SafeRAG | Summary: grounded evidence",
        metadata={"published": "2026-08-01"},
    )

    assert "published: 2026-08-01" in _format_tool_evidence(result)
