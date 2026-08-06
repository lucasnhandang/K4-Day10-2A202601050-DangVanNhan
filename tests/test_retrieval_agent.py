from __future__ import annotations

from types import SimpleNamespace

from retrieval.agent import run_agent_question


class _FakeAgent:
    def invoke(self, _payload):
        return {
            "messages": [
                SimpleNamespace(content=[{"type": "text", "text": "Grounded agent answer."}])
            ]
        }


def test_run_agent_question_normalizes_provider_content_blocks() -> None:
    assert run_agent_question(_FakeAgent(), "Question") == "Grounded agent answer."
