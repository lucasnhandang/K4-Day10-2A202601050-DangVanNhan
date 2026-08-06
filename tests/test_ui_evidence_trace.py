from __future__ import annotations

from core.config import load_settings
from retrieval.index import SearchResult
from ui import app


class _FakeIndex:
    pass


def _result(paper_id: str, title: str, score: float) -> SearchResult:
    return SearchResult(
        paper_id=paper_id,
        title=title,
        score=score,
        content="evidence",
        metadata={},
    )


def test_llm_ui_shows_only_the_agent_retrieval_trace(tmp_path, monkeypatch) -> None:
    settings = load_settings(project_dir=tmp_path)
    settings.paths.embeddings_json.parent.mkdir(parents=True, exist_ok=True)
    settings.paths.embeddings_json.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(app, "_app_settings", lambda: settings)
    monkeypatch.setattr(app.LocalEmbeddingIndex, "load", lambda *_args: _FakeIndex())

    trace_source = _result("safe-rag", "SafeRAG", 0.91)

    def fake_build_agent(_settings, _index, retrieval_trace):
        retrieval_trace.extend([trace_source, trace_source])
        return object()

    monkeypatch.setattr(app, "build_agent", fake_build_agent)
    monkeypatch.setattr(app, "run_agent_question", lambda _agent, _question: "Grounded answer")

    response = app._ask_corpus("Ai là tác giả của SafeRAG?", use_llm=True, run_key="baseline")

    assert response["status"] == "ok"
    assert response["answer"] == "Grounded answer"
    assert response["sources"] == [{"paper_id": "safe-rag", "title": "SafeRAG", "score": 0.91}]


def test_llm_ui_hides_answer_when_agent_returns_no_retrieval_trace(tmp_path, monkeypatch) -> None:
    settings = load_settings(project_dir=tmp_path)
    settings.paths.embeddings_json.parent.mkdir(parents=True, exist_ok=True)
    settings.paths.embeddings_json.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(app, "_app_settings", lambda: settings)
    monkeypatch.setattr(app.LocalEmbeddingIndex, "load", lambda *_args: _FakeIndex())
    monkeypatch.setattr(app, "build_agent", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(app, "run_agent_question", lambda _agent, _question: "Unsupported answer")

    response = app._ask_corpus("Ai là tác giả của SafeRAG?", use_llm=True, run_key="baseline")

    assert response["status"] == "unverified"
    assert "không gọi retrieval tool" in response["message"]
