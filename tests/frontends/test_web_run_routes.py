from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from mluascript.frontends.web import app as web_app
from mluascript.control.state.models import TaskLogEntryView, TaskLogsView, TaskOutputView


class FakeControlFacade:
    def __init__(self) -> None:
        self.stopped_scripts: list[str] = []
        self.stopped_pipelines: list[str] = []

    def stop_script(self, task_id: str) -> None:
        self.stopped_scripts.append(task_id)

    def stop_pipeline(self, task_id: str) -> None:
        self.stopped_pipelines.append(task_id)


class FakeStreamFacade(FakeControlFacade):
    def __init__(self) -> None:
        super().__init__()
        self.log_calls = 0
        self.output_calls = 0

    def get_task_logs(self, task_id: str) -> TaskLogsView | None:
        self.log_calls += 1
        if task_id != "task-1":
            return None
        if self.log_calls == 1:
            return TaskLogsView(task_id=task_id, items=[TaskLogEntryView(level="INFO", message="first")])
        return TaskLogsView(
            task_id=task_id,
            items=[
                TaskLogEntryView(level="INFO", message="first"),
                TaskLogEntryView(level="ERROR", message="second"),
            ],
        )

    def get_task_output(self, task_id: str) -> TaskOutputView | None:
        self.output_calls += 1
        if task_id != "task-1":
            return None
        if self.output_calls == 1:
            return TaskOutputView(task_id=task_id, items=["line 1"], max_lines=300, total_lines=1, version=1)
        return TaskOutputView(task_id=task_id, items=["line 1", "line 2"], max_lines=300, total_lines=2, version=2)


def _test_web_config() -> SimpleNamespace:
    return SimpleNamespace(
        username="admin",
        password="secret-pass",
        session_secret="0123456789abcdef",
        session_max_age_seconds=3600,
    )


def _authenticated_client(monkeypatch, tmp_path: Path) -> TestClient:
    monkeypatch.setattr(web_app, "_get_web_config", _test_web_config)
    client = TestClient(web_app.create_web_app(tmp_path))
    response = client.post("/api/auth/login", json={"username": "admin", "password": "secret-pass"})
    assert response.status_code == 200
    return client


def _read_stream_chunks(response, count: int) -> list[str]:
    iterator = response.body_iterator
    return [asyncio.run(anext(iterator)) for _ in range(count)]


def test_api_routes_require_login(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(web_app, "_get_web_config", _test_web_config)
    client = TestClient(web_app.create_web_app(tmp_path))

    response = client.get("/api/system/health")

    assert response.status_code == 401


def test_login_and_logout_update_auth_status(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(web_app, "_get_web_config", _test_web_config)
    client = TestClient(web_app.create_web_app(tmp_path))

    assert client.get("/api/auth/status").json()["data"]["authenticated"] is False
    login_response = client.post("/api/auth/login", json={"username": "admin", "password": "secret-pass"})
    assert login_response.status_code == 200
    assert client.get("/api/auth/status").json()["data"] == {"authenticated": True, "username": "admin"}
    logout_response = client.post("/api/auth/logout", json={})

    assert logout_response.status_code == 200
    assert client.get("/api/auth/status").json()["data"]["authenticated"] is False


def test_login_rejects_wrong_password(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(web_app, "_get_web_config", _test_web_config)
    client = TestClient(web_app.create_web_app(tmp_path))

    response = client.post("/api/auth/login", json={"username": "admin", "password": "bad"})

    assert response.status_code == 401


def test_stop_script_route_delegates_to_script_stop(monkeypatch, tmp_path: Path) -> None:
    facade = FakeControlFacade()
    monkeypatch.setattr(web_app, "get_control_facade", lambda: facade)
    client = _authenticated_client(monkeypatch, tmp_path)

    response = client.post("/api/run/script/script-1/stop", json={})

    assert response.status_code == 200
    assert response.json()["data"] == {"taskId": "script-1"}
    assert facade.stopped_scripts == ["script-1"]
    assert facade.stopped_pipelines == []


def test_stop_pipeline_route_delegates_to_pipeline_stop(monkeypatch, tmp_path: Path) -> None:
    facade = FakeControlFacade()
    monkeypatch.setattr(web_app, "get_control_facade", lambda: facade)
    client = _authenticated_client(monkeypatch, tmp_path)

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


def test_task_logs_stream_emits_snapshot_and_update(monkeypatch, tmp_path: Path) -> None:
    facade = FakeStreamFacade()
    monkeypatch.setattr(web_app, "get_control_facade", lambda: facade)
    response = web_app.stream_task_logs("task-1")
    snapshot, update = _read_stream_chunks(response, 2)

    assert response.media_type == "text/event-stream"
    assert "event: snapshot" in snapshot
    assert '"message": "first"' in snapshot
    assert "event: update" in update
    assert '"message": "second"' in update


def test_task_output_stream_emits_snapshot_and_update(monkeypatch, tmp_path: Path) -> None:
    facade = FakeStreamFacade()
    monkeypatch.setattr(web_app, "get_control_facade", lambda: facade)
    response = web_app.stream_task_output("task-1")
    snapshot, update = _read_stream_chunks(response, 2)

    assert response.media_type == "text/event-stream"
    assert "event: snapshot" in snapshot
    assert '"items": ["line 1"]' in snapshot
    assert "event: update" in update
    assert '"items": ["line 1", "line 2"]' in update
