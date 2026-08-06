from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import pandas as pd
from nicegui import run, ui

from core.config import Settings, load_settings
from retrieval.agent import build_agent, run_agent_question
from retrieval.index import LocalEmbeddingIndex, SearchResult
from retrieval.qa import answer_question


APP_NAME = "PaperMind"
ARTIFACT_LABELS = {
    "raw_records": "Bản chụp dữ liệu thô",
    "clean_csv": "Corpus đã làm sạch",
    "embeddings": "Embedding manifest",
    "test_set": "Bộ câu hỏi đánh giá",
    "baseline_metrics": "Metrics baseline",
    "freshness": "Báo cáo độ mới dữ liệu",
    "baseline_report": "Báo cáo baseline",
    "comparison_report": "Báo cáo so sánh",
}

METRIC_LABELS = {
    "retrieval_hit_rate": "Retrieval hit rate",
    "mean_token_f1": "Mean token F1",
    "judge_accuracy": "Judge accuracy",
    "mean_judge_score": "Mean judge score",
}


@dataclass(frozen=True)
class Artifact:
    label: str
    path: Path

    @property
    def exists(self) -> bool:
        return self.path.exists() and self.path.is_file()


@dataclass(frozen=True)
class ExperimentRun:
    """One reproducible corpus state exposed by the Phase 1/2 artifacts."""

    key: str
    label: str
    description: str
    dataframe_path: Path
    embeddings_path: Path
    metrics_path: Path
    answers_path: Path
    quality_path: Path
    freshness_path: Path


def _experiment_runs(settings: Settings) -> list[ExperimentRun]:
    paths = settings.paths
    return [
        ExperimentRun(
            key="baseline",
            label="Baseline",
            description="Corpus sạch trước khi gây lỗi dữ liệu.",
            dataframe_path=paths.clean_csv,
            embeddings_path=paths.embeddings_json,
            metrics_path=paths.baseline_metrics,
            answers_path=paths.baseline_answers,
            quality_path=paths.quality_dir / "baseline_quality.json",
            freshness_path=paths.freshness_report,
        ),
        ExperimentRun(
            key="corrupted",
            label="Dữ liệu lỗi",
            description="Corpus bị blank summary, stale date, duplicate và retrieval noise.",
            dataframe_path=paths.corrupted_clean_csv,
            embeddings_path=paths.corrupted_embeddings_json,
            metrics_path=paths.corrupted_metrics,
            answers_path=paths.corrupted_answers,
            quality_path=paths.quality_dir / "corrupted_quality.json",
            freshness_path=paths.quality_dir / "corrupted_freshness.json",
        ),
        ExperimentRun(
            key="repaired",
            label="Đã phục hồi",
            description="Corpus được cleaning lại từ raw Crossref snapshot, không dùng CSV lỗi.",
            dataframe_path=paths.repaired_clean_csv,
            embeddings_path=paths.repaired_embeddings_json,
            metrics_path=paths.repaired_metrics,
            answers_path=paths.repaired_answers,
            quality_path=paths.quality_dir / "repaired_quality.json",
            freshness_path=paths.quality_dir / "repaired_freshness.json",
        ),
    ]


def _artifact_inventory(settings: Settings) -> list[Artifact]:
    paths = settings.paths
    return [
        Artifact(ARTIFACT_LABELS["raw_records"], paths.raw_records_json),
        Artifact(ARTIFACT_LABELS["clean_csv"], paths.clean_csv),
        Artifact(ARTIFACT_LABELS["embeddings"], paths.embeddings_json),
        Artifact(ARTIFACT_LABELS["test_set"], paths.eval_testset),
        Artifact(ARTIFACT_LABELS["baseline_metrics"], paths.baseline_metrics),
        Artifact(ARTIFACT_LABELS["freshness"], paths.freshness_report),
        Artifact(ARTIFACT_LABELS["baseline_report"], paths.baseline_report),
        Artifact(ARTIFACT_LABELS["comparison_report"], paths.comparison_report),
    ]


def _read_json(path: Path) -> Any | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _read_dataframe(path: Path) -> pd.DataFrame | None:
    if not path.is_file():
        return None
    try:
        return pd.read_csv(path)
    except (OSError, pd.errors.ParserError, UnicodeDecodeError):
        return None


def _format_metric(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.3f}" if isinstance(value, float) else str(value)
    return "—"


def _display_metric(metric: str, value: Any) -> str:
    """Format persisted metrics with their actual units for the demo UI."""
    if not isinstance(value, (int, float)):
        return "—"
    if metric in {"retrieval_hit_rate", "judge_accuracy"}:
        return f"{value:.1%}"
    if metric == "mean_judge_score":
        return f"{value:.2f}/5"
    return f"{value:.4f}"


def _metric_delta(metric: str, current: Any, reference: Any) -> str:
    if not isinstance(current, (int, float)) or not isinstance(reference, (int, float)):
        return "—"
    delta = current - reference
    if metric in {"retrieval_hit_rate", "judge_accuracy"}:
        return f"{delta * 100:+.1f} điểm %"
    return f"{delta:+.4f}"


def _empty_artifact(path: Path, action: str) -> None:
    with ui.card().classes("empty-artifact w-full"):
        ui.icon("inventory_2", size="28px").classes("empty-icon")
        ui.label("Chưa có artifact").classes("empty-title")
        ui.label(action).classes("empty-copy")
        ui.label(str(path)).classes("artifact-path")


def _section_heading(kicker: str, title: str, copy: str) -> None:
    ui.label(kicker).classes("eyebrow")
    ui.label(title).classes("page-title")
    ui.label(copy).classes("page-copy")


def _metric_card(label: str, value: Any, note: str = "") -> None:
    with ui.card().classes("metric-card"):
        ui.label(label).classes("metric-label")
        ui.label(value if isinstance(value, str) else _format_metric(value)).classes("metric-value")
        if note:
            ui.label(note).classes("metric-note")


def _shell(active: str) -> None:
    drawer = ui.left_drawer(value=True).classes("app-drawer")
    drawer.props["width"] = 360
    sidebar_compact = {"value": False}
    sidebar_toggle_buttons: list[ui.button] = []

    def toggle_sidebar() -> None:
        sidebar_compact["value"] = not sidebar_compact["value"]
        drawer.props["width"] = 84 if sidebar_compact["value"] else 360
        drawer.classes(
            add="drawer-compact" if sidebar_compact["value"] else "drawer-expanded",
            remove="drawer-expanded" if sidebar_compact["value"] else "drawer-compact",
        )
        new_icon = "chevron_right" if sidebar_compact["value"] else "chevron_left"
        for button in sidebar_toggle_buttons:
            button.props(f"icon={new_icon}")

    with ui.header().classes("app-header"):
        with ui.row().classes("w-full items-center justify-between no-wrap"):
            with ui.row().classes("items-center no-wrap gap-3"):
                ui.icon("auto_stories", size="24px").classes("brand-icon")
                with ui.column().classes("gap-0"):
                    ui.label(APP_NAME).classes("brand-name")
                    ui.label("TRỢ LÝ NGHIÊN CỨU HỌC THUẬT").classes("brand-subtitle")
            ui.badge("LAB DATA PIPELINE").classes("lab-badge")

    with drawer:
        with ui.row().classes("w-full items-center justify-between no-wrap drawer-topbar"):
            ui.label("GHI CHÚ NGHIÊN CỨU").classes("drawer-kicker")
            sidebar_toggle_button = ui.button(icon="chevron_left", on_click=toggle_sidebar).props(
                "flat round dense color=white"
            ).classes("drawer-inline-toggle")
        sidebar_toggle_buttons.append(sidebar_toggle_button)
        ui.label("Bằng chứng khoa học, luôn có thể kiểm chứng.").classes("drawer-title")
        navigation = [
            ("RAG Research Assistant", "forum", "/rag"),
            ("Data Health", "assessment", "/data-health"),
            ("Experiment Comparison", "science", "/comparison"),
        ]
        with ui.column().classes("nav-list w-full"):
            for label, icon, target in navigation:
                classes = "nav-item-active" if target == active else "nav-item"
                with ui.element("button").classes(classes) as nav_item:
                    with ui.element("span").classes("nav-icon-slot"):
                        ui.icon(icon, size="20px").classes("nav-item-icon")
                    ui.label(label).classes("nav-item-label")
                nav_item.on("click", lambda route=target: ui.navigate.to(route))
        ui.space()
        ui.separator().classes("drawer-rule")
        ui.label("PaperMind chỉ hiển thị artifact thực sự có trong workspace.").classes("drawer-footnote")


def _app_settings() -> Settings:
    return load_settings()


def _serialize_sources(results: list[SearchResult]) -> list[dict[str, Any]]:
    """Return one UI source per document, preserving the agent tool order."""
    seen: set[str] = set()
    sources: list[dict[str, Any]] = []
    for result in results:
        if result.paper_id in seen:
            continue
        seen.add(result.paper_id)
        sources.append(
            {
                "paper_id": result.paper_id,
                "title": result.title,
                "score": result.score,
            }
        )
    return sources


def _ask_corpus(question: str, use_llm: bool, run_key: str) -> dict[str, Any]:
    settings = _app_settings()
    runs = {run.key: run for run in _experiment_runs(settings)}
    selected_run = runs.get(run_key)
    if selected_run is None:
        return {"status": "error", "message": f"Trạng thái corpus không hợp lệ: {run_key}"}
    manifest = selected_run.embeddings_path
    if not manifest.is_file():
        return {"status": "missing", "path": manifest, "run": selected_run.label}

    try:
        index = LocalEmbeddingIndex.load(settings, manifest)

        if use_llm:
            retrieval_trace: list[SearchResult] = []
            answer = run_agent_question(
                build_agent(settings, index, retrieval_trace=retrieval_trace),
                question,
            )
            sources = _serialize_sources(retrieval_trace)
            if not sources:
                return {
                    "status": "unverified",
                    "message": (
                        "LLM agent không gọi retrieval tool, nên PaperMind không hiển thị "
                        "câu trả lời không có bằng chứng từ corpus."
                    ),
                    "run": selected_run.label,
                    "manifest": manifest,
                }
            mode = "LLM agent được grounding bằng corpus cục bộ"
        else:
            result = answer_question(question, settings, index)
            answer = result.answer
            sources = [
                {"paper_id": paper_id, "title": title, "score": None}
                for paper_id, title in zip(result.retrieved_doc_ids, result.retrieved_titles, strict=False)
            ]
            if not sources:
                return {
                    "status": "empty",
                    "answer": "Không tìm thấy tài liệu liên quan trong corpus đã index.",
                    "sources": [],
                }
            mode = "Câu trả lời trích xuất từ bài báo được truy xuất cao nhất"

        return {
            "status": "ok",
            "answer": answer,
            "mode": mode,
            "run": selected_run.label,
            "manifest": manifest,
            "sources": sources,
        }
    except Exception as exc:  # UI must expose unavailable models/providers rather than mask them.
        return {"status": "error", "message": str(exc)}


def _render_sources(sources: list[dict[str, Any]]) -> None:
    ui.label("Bằng chứng agent đã dùng").classes("sources-heading")
    for item in sources:
        with ui.card().classes("source-card w-full"):
            with ui.row().classes("w-full justify-between items-start no-wrap"):
                with ui.column().classes("gap-1"):
                    ui.label(item["title"]).classes("source-title")
                    ui.label(item["paper_id"]).classes("source-id")
                score = item.get("score")
                ui.badge(f"{score:.2f}" if isinstance(score, (int, float)) else "truy xuất").classes("score-badge")


@ui.page("/")
def home_page() -> None:
    configure_page()
    ui.navigate.to("/rag")


@ui.page("/rag")
def rag_page() -> None:
    configure_page()
    _shell("/rag")
    settings = _app_settings()
    runs = _experiment_runs(settings)
    runs_by_key = {run.key: run for run in runs}
    with ui.column().classes("page-wrap"):
        _section_heading(
            "TRỢ LÝ NGHIÊN CỨU",
            "Hỏi corpus. Kiểm chứng bằng chứng.",
            "PaperMind chỉ trả lời dựa trên bộ sưu tập học thuật cục bộ và luôn hiển thị các bài báo đã truy xuất.",
        )
        if not any(run.embeddings_path.is_file() for run in runs):
            _empty_artifact(
                settings.paths.embeddings_json,
                "Chạy baseline pipeline để tạo ít nhất một Chroma collection trước khi đặt câu hỏi cho PaperMind.",
            )
            return

        with ui.card().classes("query-card w-full"):
            ui.label("Đặt câu hỏi cho bộ sưu tập bài báo đã index").classes("query-title")
            ui.label("Chọn trạng thái thí nghiệm rồi hỏi về tác giả, ngày xuất bản, chủ đề hoặc tóm tắt.").classes("query-copy")
            selected_run = ui.select(
                options={run.key: run.label for run in runs},
                value="baseline",
                label="Corpus dùng để trả lời",
            ).classes("run-select w-full")
            run_context = ui.label("").classes("run-context")

            def refresh_run_context() -> None:
                run = runs_by_key[selected_run.value]
                availability = "Sẵn sàng" if run.embeddings_path.is_file() else "Chưa có embedding manifest"
                run_context.set_text(f"{run.description} · {availability}")

            selected_run.on_value_change(lambda _: refresh_run_context())
            refresh_run_context()
            question = ui.textarea(placeholder="Ví dụ: Ai là tác giả của '…'?").classes("question-input w-full")
            use_llm = ui.switch("Dùng LLM agent đã cấu hình", value=False).classes("llm-switch")
            results = ui.column().classes("answer-area w-full")

            async def submit_question() -> None:
                prompt = (question.value or "").strip()
                if not prompt:
                    ui.notify("Hãy nhập câu hỏi trước.", type="warning")
                    return
                results.clear()
                with results:
                    with ui.card().classes("user-question w-full"):
                        ui.label("CÂU HỎI CỦA BẠN").classes("answer-kicker")
                        ui.label(prompt).classes("question-text")
                    with ui.spinner(size="lg").classes("self-center"):
                        response = await run.io_bound(_ask_corpus, prompt, use_llm.value, selected_run.value)
                    if response["status"] == "missing":
                        _empty_artifact(response["path"], f"RAG cần embedding manifest của trạng thái {response['run']}.")
                    elif response["status"] == "error":
                        with ui.card().classes("error-card w-full"):
                            ui.label("PaperMind chưa thể hoàn thành yêu cầu này.").classes("error-title")
                            ui.label(response["message"]).classes("error-copy")
                    elif response["status"] == "unverified":
                        with ui.card().classes("error-card w-full"):
                            ui.label("Không thể xác minh bằng chứng cho câu trả lời.").classes("error-title")
                            ui.label(response["message"]).classes("error-copy")
                    else:
                        with ui.card().classes("answer-card w-full"):
                            ui.label(f"CÂU TRẢ LỜI — {response['run'].upper()}").classes("answer-kicker")
                            ui.label(response["answer"]).classes("answer-text")
                            ui.label(response.get("mode", "")).classes("answer-mode")
                            ui.label(str(response["manifest"])).classes("artifact-path")
                        _render_sources(response["sources"])

            ui.button("Hỏi PaperMind", icon="arrow_forward", on_click=submit_question).classes("ask-button")


@ui.page("/data-health")
def data_health_page() -> None:
    configure_page()
    _shell("/data-health")
    settings = _app_settings()
    with ui.column().classes("page-wrap"):
        _section_heading(
            "SỨC KHỎE DỮ LIỆU",
            "Hiểu corpus trước khi tin vào câu trả lời.",
            "Bản chụp dữ liệu thô, quality checks và tín hiệu freshness được đọc trực tiếp từ artifact của pipeline.",
        )
        inventory = _artifact_inventory(settings)
        with ui.row().classes("status-grid w-full"):
            for artifact in inventory:
                with ui.card().classes("artifact-status"):
                    ui.icon("check_circle" if artifact.exists else "hourglass_empty").classes(
                        "status-ok" if artifact.exists else "status-pending"
                    )
                    ui.label(artifact.label).classes("status-label")
                    ui.label("Sẵn sàng" if artifact.exists else "Chưa có artifact").classes("status-value")

        frame = _read_dataframe(settings.paths.clean_csv)
        if frame is None:
            _empty_artifact(settings.paths.clean_csv, "Chạy phase 1 để tạo corpus đã làm sạch và phần tóm tắt sức khỏe dữ liệu.")
        else:
            ui.label("Bản chụp corpus đã làm sạch").classes("section-title")
            with ui.row().classes("metric-grid w-full"):
                _metric_card("Bản ghi", len(frame), "dòng trong cleaned CSV")
                _metric_card("Paper ID duy nhất", frame["paper_id"].nunique() if "paper_id" in frame else None)
                _metric_card("Tóm tắt bị thiếu", int(frame["summary"].isna().sum()) if "summary" in frame else None)
                _metric_card("Paper ID trùng", int(frame["paper_id"].duplicated().sum()) if "paper_id" in frame else None)
            columns = [
                {"name": key, "label": label, "field": key, "align": "left"}
                for key, label in (("paper_id", "Paper ID"), ("title", "Tiêu đề"), ("published", "Xuất bản"), ("age_days", "Số ngày tuổi"))
                if key in frame.columns
            ]
            if columns:
                ui.table(columns=columns, rows=frame[[item["name"] for item in columns]].head(8).fillna("").to_dict("records"), row_key="paper_id").classes("paper-table w-full")

        freshness = _read_json(settings.paths.freshness_report)
        if freshness is None:
            _empty_artifact(settings.paths.freshness_report, "Báo cáo độ mới sẽ xuất hiện sau bước quality của phase 1.")
        else:
            ui.label("Tín hiệu độ mới dữ liệu").classes("section-title")
            with ui.card().classes("freshness-card w-full"):
                ui.label("Báo cáo độ mới đọc từ artifact của pipeline").classes("freshness-title")
                ui.code(json.dumps(freshness, indent=2, ensure_ascii=False), language="json").classes("w-full")


@ui.page("/comparison")
def comparison_page() -> None:
    configure_page()
    _shell("/comparison")
    settings = _app_settings()
    with ui.column().classes("page-wrap"):
        _section_heading(
            "SO SÁNH THÍ NGHIỆM",
            "Quan sát suy giảm. Xác minh phục hồi.",
            "Cả ba trạng thái phải dùng cùng một evaluation set; PaperMind không suy diễn metric còn thiếu.",
        )
        runs = _experiment_runs(settings)
        metrics_by_run = {run.key: _read_json(run.metrics_path) for run in runs}
        with ui.row().classes("metric-grid w-full"):
            for experiment in runs:
                payload = metrics_by_run[experiment.key]
                with ui.card().classes("run-card"):
                    ui.label(experiment.label.upper()).classes("run-label")
                    if payload is None:
                        ui.label("Chưa có artifact").classes("run-missing")
                        ui.label(str(experiment.metrics_path)).classes("artifact-path")
                    else:
                        ui.label(_display_metric("retrieval_hit_rate", payload.get("retrieval_hit_rate"))).classes("run-value")
                        ui.label("tỷ lệ retrieval hit").classes("metric-note")

        available = {
            experiment.key: payload
            for experiment, payload in ((run, metrics_by_run[run.key]) for run in runs)
            if isinstance(payload, dict)
        }
        if not available:
            _empty_artifact(
                settings.paths.baseline_metrics,
                "Chạy baseline flow và corruption flow để phần so sánh có metric thật.",
            )
            return

        baseline = available.get("baseline")
        if baseline is not None:
            with ui.row().classes("metric-grid w-full"):
                for key in ("retrieval_hit_rate", "mean_token_f1", "judge_accuracy"):
                    corrupted = available.get("corrupted", {})
                    repaired = available.get("repaired", {})
                    _metric_card(
                        f"{METRIC_LABELS[key]} · lỗi so baseline",
                        _metric_delta(key, corrupted.get(key), baseline.get(key)),
                        f"Phục hồi: {_metric_delta(key, repaired.get(key), baseline.get(key))}",
                    )

        ui.label("Bảng metric").classes("section-title")
        metric_keys = list(METRIC_LABELS)
        rows = [
            {
                "metric": METRIC_LABELS[metric],
                **{
                    next(run.label for run in runs if run.key == name): _display_metric(metric, payload.get(metric))
                    for name, payload in available.items()
                },
            }
            for metric in metric_keys
        ]
        columns = [{"name": "metric", "label": "Metric", "field": "metric", "align": "left"}] + [
            {
                "name": run.label,
                "label": run.label,
                "field": run.label,
                "align": "right",
            }
            for run in runs
            if run.key in available
        ]
        ui.table(columns=columns, rows=rows, row_key="metric").classes("comparison-table w-full")

        chart_runs = [run for run in runs if run.key in available]
        if chart_runs:
            ui.label("Biểu đồ retrieval hit rate").classes("section-title")
            ui.echart(
                {
                    "tooltip": {"trigger": "axis"},
                    "xAxis": {"type": "category", "data": [run.label for run in chart_runs]},
                    "yAxis": {"type": "value", "min": 0, "max": 100, "axisLabel": {"formatter": "{value}%"}},
                    "series": [
                        {
                            "name": "Retrieval hit rate",
                            "type": "bar",
                            "data": [available[run.key].get("retrieval_hit_rate", 0) * 100 for run in chart_runs],
                            "itemStyle": {"color": "#813f39"},
                            "label": {"show": True, "formatter": "{c}%"},
                        }
                    ],
                }
            ).classes("chart-card w-full")

        comparison = settings.paths.comparison_report
        if comparison.is_file():
            ui.label("Báo cáo so sánh").classes("section-title")
            ui.markdown(comparison.read_text(encoding="utf-8")).classes("report-card w-full")
        else:
            _empty_artifact(comparison, "Tạo báo cáo so sánh sau khi evaluation của dữ liệu đã phục hồi hoàn tất.")


def configure_page() -> None:
    ui.add_head_html(
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Merriweather:wght@400;700&display=swap" rel="stylesheet">'
    )
    ui.colors(primary="#19344d", secondary="#a44a3f", accent="#bd8d3a", positive="#2f6d62")
    ui.add_css(
        """
        :root { --ink: #19344d; --wine: #813f39; --brass: #bd8d3a; --paper: #f4eee1; --card: #fffaf0; --muted: #66727d; }
        body { background: var(--paper); color: var(--ink); font-family: Inter, ui-sans-serif, system-ui, sans-serif; }
        .q-page-container { background: radial-gradient(circle at 85% 8%, #e7d8bc 0, transparent 29%), var(--paper); }
        .app-header { background: rgba(25, 52, 77, .98); color: #fffaf0; padding: 10px 26px; }
        .brand-name, .page-title, .drawer-title, .section-title, .sources-heading, .empty-title { font-family: Merriweather, Georgia, 'Times New Roman', serif; }
        .brand-name { font-size: 22px; letter-spacing: .03em; font-weight: 700; }
        .brand-subtitle, .eyebrow, .drawer-kicker, .answer-kicker { font-size: 10px; letter-spacing: .15em; font-weight: 800; }
        .brand-subtitle { color: #d8c59e; } .brand-icon { color: #d8b66f; } .lab-badge { background: #bd8d3a; color: #1b334b; font-weight: 800; }
        .app-drawer { background: #173147; color: #f7efe0; padding: 28px 18px; transition: width .22s ease, padding .22s ease; }
        .drawer-topbar { margin-bottom: 10px; } .drawer-kicker { color: #d9b76f; } .drawer-title { font-size: 21px; line-height: 1.15; margin: 10px 0 28px; }
        .drawer-inline-toggle.q-btn { flex-shrink: 0; }
        .nav-list { gap: 8px; } .nav-item, .nav-item-active { display: grid; grid-template-columns: 32px minmax(0, 1fr); align-items: center; width: 100%; min-height: 52px; padding: 10px 12px; border: 0; border-radius: 8px; box-shadow: 0 4px 10px rgba(7,25,39,.25); cursor: pointer; column-gap: 12px; font: inherit; font-weight: 650; text-align: left; }
        .nav-item { background: #1d405c; color: #dfe5e7; } .nav-item:hover { background: #244b6a; } .nav-item-active { background: #f4eee1; color: #19344d; }
        .nav-icon-slot { display: flex; grid-column: 1; width: 32px; min-width: 32px; height: 32px; align-items: center; justify-content: center; justify-self: center; overflow: hidden; } .nav-item-icon { display: inline-flex; width: 20px; min-width: 20px; height: 20px; flex: 0 0 20px; align-items: center; justify-content: center; font-size: 20px !important; line-height: 20px !important; overflow: hidden; }
        .nav-item-label { grid-column: 2; min-width: 0; line-height: 1.25; } .nav-item .nav-item-icon { color: #d9b76f; } .nav-item-active .nav-item-icon { color: #813f39; }
        .drawer-compact { padding: 28px 12px; } .drawer-compact .drawer-kicker, .drawer-compact .drawer-title, .drawer-compact .drawer-footnote, .drawer-compact .drawer-rule { display: none; }
        .drawer-compact .drawer-topbar { justify-content: center; margin-bottom: 18px; }
        .drawer-compact .nav-list { margin-top: 2px; } .drawer-compact .nav-item, .drawer-compact .nav-item-active { grid-template-columns: 1fr; padding: 10px; justify-items: center; }
        .drawer-compact .nav-icon-slot { grid-column: 1; } .drawer-compact .nav-item-label { display: none; }
        .drawer-rule { background: rgba(255,255,255,.18); } .drawer-footnote { color: #aac0c8; font-size: 12px; line-height: 1.45; }
        .page-wrap { width: min(1120px, calc(100vw - 88px)); margin: 0 auto; padding: 64px 28px 80px; gap: 20px; }
        .eyebrow { color: var(--wine); } .page-title { font-size: clamp(34px, 5vw, 58px); line-height: 1.16; max-width: 760px; padding-top: .08em; font-weight: 700; }
        .page-copy { font-size: 16px; line-height: 1.65; color: var(--muted); max-width: 760px; }
        .q-card { box-shadow: 0 8px 28px rgba(25,52,77,.09); } .query-card, .answer-card, .user-question, .freshness-card, .report-card { background: var(--card); border: 1px solid #e1d6be; border-radius: 14px; padding: 24px; }
        .query-title, .section-title { font-family: Merriweather, Georgia, 'Times New Roman', serif; font-size: 24px; font-weight: 700; } .query-copy, .metric-note, .answer-mode, .run-context { color: var(--muted); font-size: 13px; } .run-context { margin-top: -4px; line-height: 1.45; }
        .question-input textarea { min-height: 95px; } .llm-switch { color: var(--ink); } .ask-button { background: var(--wine); color: #fffaf0; border-radius: 8px; padding: 8px 18px; font-weight: 800; }
        .answer-area { gap: 16px; } .user-question { background: #e7edf0; border-color: #cbd8dc; } .answer-kicker { color: var(--wine); } .question-text, .answer-text { white-space: pre-wrap; line-height: 1.65; font-size: 16px; }
        .sources-heading { font-family: Merriweather, Georgia, 'Times New Roman', serif; font-size: 20px; font-weight: 700; } .source-card { background: #fffaf0; border-left: 4px solid var(--brass); padding: 14px; }
        .source-title { font-weight: 750; } .source-id, .artifact-path { color: var(--muted); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11px; overflow-wrap: anywhere; } .score-badge { background: #d9b76f; color: #19344d; font-weight: 800; }
        .empty-artifact { background: #f9f2e5; border: 1px dashed #b99f70; border-radius: 14px; padding: 24px; align-items: flex-start; } .empty-icon { color: var(--brass); } .empty-title { font-family: Merriweather, Georgia, 'Times New Roman', serif; font-size: 21px; font-weight: 700; } .empty-copy { color: var(--muted); }
        .error-card { background: #f8e7e2; border: 1px solid #d79c91; padding: 20px; } .error-title { color: #813f39; font-weight: 800; } .error-copy { color: #5b302d; overflow-wrap: anywhere; }
        .status-grid, .metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; } .artifact-status, .metric-card, .run-card { background: var(--card); padding: 17px; min-width: 0; }
        .status-ok { color: #2f6d62; } .status-pending { color: #b99f70; } .status-label, .metric-label, .run-label { font-size: 12px; color: var(--muted); font-weight: 750; text-transform: uppercase; letter-spacing: .06em; } .status-value { font-family: Georgia, serif; font-size: 18px; margin-top: 7px; }
        .metric-value, .run-value { font-family: Georgia, serif; font-size: 32px; color: var(--ink); margin-top: 10px; } .run-missing { color: var(--wine); font-weight: 700; margin: 10px 0; }
        .paper-table, .comparison-table, .chart-card { background: #fffaf0; } .chart-card { min-height: 300px; padding: 12px; border: 1px solid #e1d6be; border-radius: 14px; } .freshness-title { font-weight: 750; margin-bottom: 12px; }
        @media (max-width: 800px) { .page-wrap { width: 100%; padding: 42px 20px 64px; } .status-grid, .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
        """
    )


def run_app() -> None:
    ui.run(title=APP_NAME, favicon="📚", reload=False)
