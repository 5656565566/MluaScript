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


def test_editor_session_isolated_per_authenticated_client(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(web_app, "_get_web_config", _test_web_config)
    monkeypatch.chdir(tmp_path)

    client_a = TestClient(web_app.create_web_app(tmp_path))
    client_b = TestClient(web_app.create_web_app(tmp_path))

    assert client_a.post("/api/auth/login", json={"username": "admin", "password": "secret-pass"}).status_code == 200
    assert client_b.post("/api/auth/login", json={"username": "admin", "password": "secret-pass"}).status_code == 200

    session_a = {
        "blocklyDocument": {"xml": "<xml>a</xml>", "filename": "a.xml", "path": "a.xml"},
        "luaDocument": {"content": "print('a')", "filename": "a.lua", "path": "a.lua"},
    }
    session_b = {
        "blocklyDocument": {"xml": "<xml>b</xml>", "filename": "b.xml", "path": "b.xml"},
        "luaDocument": {"content": "print('b')", "filename": "b.lua", "path": "b.lua"},
    }

    assert client_a.put("/api/editor/session", json=session_a).status_code == 200
    assert client_b.put("/api/editor/session", json=session_b).status_code == 200

    response_a = client_a.get("/api/editor/session")
    response_b = client_b.get("/api/editor/session")

    assert response_a.status_code == 200
    assert response_b.status_code == 200
    assert response_a.json()["data"]["luaDocument"]["path"] == "a.lua"
    assert response_b.json()["data"]["luaDocument"]["path"] == "b.lua"
    assert response_a.json()["data"]["blocklyDocument"]["xml"] == "<xml>a</xml>"
    assert response_b.json()["data"]["blocklyDocument"]["xml"] == "<xml>b</xml>"


def test_editor_session_sync_preserves_file_metadata(monkeypatch, tmp_path: Path) -> None:
    client = _authenticated_client(monkeypatch, tmp_path)
    payload = {
        "blocklyDocument": {
            "xml": "<xml />",
            "filename": "main.xml",
            "path": "main.xml",
            "mtime": 12.5,
            "saveMode": "update",
            "dirty": False,
        },
        "luaDocument": {
            "content": "print('ok')",
            "filename": "main.lua",
            "path": "main.lua",
            "mtime": 23.5,
            "saveMode": "update",
            "dirty": False,
        },
    }

    response = client.put("/api/editor/session", json=payload)

    assert response.status_code == 200
    session = response.json()["data"]
    assert session["blocklyDocument"]["mtime"] == 12.5
    assert session["blocklyDocument"]["saveMode"] == "update"
    assert session["blocklyDocument"]["dirty"] is False
    assert session["luaDocument"]["mtime"] == 23.5
    assert session["luaDocument"]["saveMode"] == "update"
    assert session["luaDocument"]["dirty"] is False


def test_update_lua_file_with_previous_path_renames_existing_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(web_app, "_get_web_config", _test_web_config)
    monkeypatch.chdir(tmp_path)
    client = _authenticated_client(monkeypatch, tmp_path)

    create_response = client.post("/api/editor/lua/files", json={"path": "scripts/original.lua", "content": "print('old')"})
    assert create_response.status_code == 200
    created = create_response.json()["data"]

    update_response = client.put(
        "/api/editor/lua/files/content",
        json={
            "path": "scripts/renamed.lua",
            "previousPath": "scripts/original.lua",
            "content": "print('new')",
            "expectedMtime": created["mtime"],
        },
    )

    assert update_response.status_code == 200
    payload = update_response.json()["data"]
    assert payload["path"] == "scripts/renamed.lua"
    assert not (tmp_path / ".mluascript_web" / "lua" / "scripts" / "original.lua").exists()
    renamed_file = tmp_path / ".mluascript_web" / "lua" / "scripts" / "renamed.lua"
    assert renamed_file.exists()
    assert renamed_file.read_text(encoding="utf-8") == "print('new')"


def test_update_lua_file_rejects_rename_to_existing_target(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(web_app, "_get_web_config", _test_web_config)
    monkeypatch.chdir(tmp_path)
    client = _authenticated_client(monkeypatch, tmp_path)

    source_response = client.post("/api/editor/lua/files", json={"path": "source.lua", "content": "print('source')"})
    assert source_response.status_code == 200
    existing_response = client.post("/api/editor/lua/files", json={"path": "target.lua", "content": "print('target')"})
    assert existing_response.status_code == 200

    conflict_response = client.put(
        "/api/editor/lua/files/content",
        json={
            "path": "target.lua",
            "previousPath": "source.lua",
            "content": "print('new')",
            "expectedMtime": source_response.json()["data"]["mtime"],
        },
    )

    assert conflict_response.status_code == 409
    assert conflict_response.json()["detail"] == "目标文件已存在"


def test_store_guards_editor_session_replay_when_local_draft_exists() -> None:
    session_file = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "mluascript_web"
        / "src"
        / "features"
        / "editor"
        / "editorSession.js"
    )
    source = session_file.read_text(encoding="utf-8")

    assert "editorSessionHydrated" in source
    assert "hasUnsyncedBlocklyDraft" in source
    assert "hasUnsyncedLuaDraft" in source
    assert "const shouldApplyBlockly = !state.editorSessionHydrated.value || !hasUnsyncedBlocklyDraft(state)" in source
    assert "const shouldApplyLua = !state.editorSessionHydrated.value || !hasUnsyncedLuaDraft(state)" in source


def test_vision_roi_block_generates_lua_table_instead_of_string() -> None:
    vision_file = Path(__file__).resolve().parents[2] / "src" / "mluascript_web" / "src" / "blockly" / "blocks" / "vision.js"
    source = vision_file.read_text(encoding="utf-8")

    assert "output: MAA_ROI_TYPE" in source
    assert "return [`{${x}, ${y}, ${w}, ${h}}`, luaOrder]" in source
    assert "return ['nil', luaOrder]" in source
    assert "check: MAA_ROI_TYPE" in source
