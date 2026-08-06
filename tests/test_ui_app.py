from __future__ import annotations

from core.config import load_settings
from ui.app import _display_metric, _experiment_runs, _metric_delta


def test_experiment_runs_bind_each_ui_state_to_its_own_artifacts(tmp_path) -> None:
    settings = load_settings(project_dir=tmp_path)

    runs = {run.key: run for run in _experiment_runs(settings)}

    assert set(runs) == {"baseline", "corrupted", "repaired"}
    assert runs["baseline"].embeddings_path == settings.paths.embeddings_json
    assert runs["corrupted"].embeddings_path == settings.paths.corrupted_embeddings_json
    assert runs["repaired"].embeddings_path == settings.paths.repaired_embeddings_json
    assert runs["repaired"].dataframe_path == settings.paths.repaired_clean_csv


def test_ui_metric_display_preserves_metric_units() -> None:
    assert _display_metric("retrieval_hit_rate", 0.7) == "70.0%"
    assert _display_metric("mean_token_f1", 0.171737) == "0.1717"
    assert _display_metric("mean_judge_score", 3.5) == "3.50/5"
    assert _metric_delta("retrieval_hit_rate", 0.7, 0.9) == "-20.0 điểm %"
    assert _metric_delta("mean_token_f1", 0.1981, 0.1930) == "+0.0051"
