from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from mluascript.frontends.web import app as web_app


class FakeControlFacade:
    def __init__(self) -> None:
        self.stopped_scripts: list[str] = []
        self.stopped_pipelines: list[str] = []

    def stop_script(self, task_id: str) -> None:
        self.stopped_scripts.append(task_id)

    def stop_pipeline(self, task_id: str) -> None:
        self.stopped_pipelines.append(task_id)


def test_stop_script_route_delegates_to_script_stop(monkeypatch, tmp_path: Path) -> None:
    facade = FakeControlFacade()
    monkeypatch.setattr(web_app, "get_control_facade", lambda: facade)
    client = TestClient(web_app.create_web_app(tmp_path))

    response = client.post("/api/run/script/script-1/stop", json={})

    assert response.status_code == 200
    assert response.json()["data"] == {"taskId": "script-1"}
    assert facade.stopped_scripts == ["script-1"]
    assert facade.stopped_pipelines == []


def test_stop_pipeline_route_delegates_to_pipeline_stop(monkeypatch, tmp_path: Path) -> None:
    facade = FakeControlFacade()
    monkeypatch.setattr(web_app, "get_control_facade", lambda: facade)
    client = TestClient(web_app.create_web_app(tmp_path))

    response = client.post("/api/run/pipeline/pipeline-1/stop", json={})

    assert response.status_code == 200
    assert response.json()["data"] == {"taskId": "pipeline-1"}
    assert facade.stopped_scripts == []
    assert facade.stopped_pipelines == ["pipeline-1"]


def test_task_detail_views_pass_task_kind_to_stop_action() -> None:
    web_src = Path(__file__).resolve().parents[2] / "src" / "mluascript_web" / "src" / "components"

    manager_view = (web_src / "TaskManagerView.vue").read_text(encoding="utf-8")
    detail_modal = (web_src / "TaskDetailModal.vue").read_text(encoding="utf-8")

    assert "actions.stopTask(taskDetail.task_id, taskDetail.kind)" in manager_view
    assert "actions.stopTask(task.task_id, task.kind)" in detail_modal
