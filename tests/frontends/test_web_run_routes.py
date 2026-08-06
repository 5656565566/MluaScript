from __future__ import annotations

import asyncio
import hashlib
import zipfile
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
import yaml

from mluascript.frontends.web import app as web_app
from mluascript.control.state.models import TaskLogEntryView, TaskLogsView, TaskOutputView


class FakeControlFacade:
    def __init__(self) -> None:
        self.stopped_scripts: list[str] = []
        self.stopped_pipelines: list[str] = []
        self.tasks = {
            "script-1": self._task("script-1", "script"),
            "pipeline-1": self._task("pipeline-1", "pipeline"),
        }

    @staticmethod
    def _task(task_id: str, kind: str, status: str = "running") -> SimpleNamespace:
        return SimpleNamespace(
            task_id=task_id,
            kind=kind,
            status=status,
            capabilities=SimpleNamespace(can_stop=status == "running"),
        )

    def get_task_detail_view(self, task_id: str) -> SimpleNamespace | None:
        return self.tasks.get(task_id)

    def stop_script(self, task_id: str) -> None:
        self.stopped_scripts.append(task_id)
        self.tasks[task_id] = self._task(task_id, "script", "stopped")

    def stop_pipeline(self, task_id: str) -> None:
        self.stopped_pipelines.append(task_id)
        self.tasks[task_id] = self._task(task_id, "pipeline", "stopped")


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


class FakeRunFacade(FakeControlFacade):
    def __init__(self) -> None:
        super().__init__()
        self.run_script_calls: list[tuple[str, str, str]] = []

    def get_device_overview(self) -> SimpleNamespace:
        return SimpleNamespace(connection=SimpleNamespace(label="LOCAL"))

    def run_script(self, script_path: str, code: str, target: str) -> str:
        self.run_script_calls.append((script_path, code, target))
        return "run-1"


class FakeArtifactRunFacade(FakeRunFacade):
    def __init__(self) -> None:
        super().__init__()
        self.artifact_run_calls: list[dict[str, object]] = []

    def run_script(
        self,
        script_path: str,
        code: str,
        target: str,
        *,
        title: str | None = None,
        summary: dict[str, object] | None = None,
        cleanup_dir: str | None = None,
    ) -> str:
        self.artifact_run_calls.append(
            {
                "script_path": script_path,
                "code": code,
                "target": target,
                "title": title,
                "summary": summary,
                "cleanup_dir": cleanup_dir,
            }
        )
        return "artifact-run-1"


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


def _write_readme_package(path: Path) -> None:
    manifest = {
        "schema": "mluascript.package/v1",
        "type": "lua-package",
        "package": {"id": "com.example.readme", "name": "说明包", "version": "1.0.0"},
        "entrypoints": {"main": {"script": "scripts/main.lua"}},
    }
    files = {
        "mluascript.yaml": yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True).encode("utf-8"),
        "README.md": "# 说明包\n\n安全说明。\n".encode("utf-8"),
        "scripts/main.lua": b"return true\n",
    }
    checksums = "".join(
        f"{hashlib.sha256(content).hexdigest()}  {relative}\n"
        for relative, content in sorted(files.items())
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("META-INF/files.sha256", checksums)
        for relative, content in files.items():
            archive.writestr(relative, content)


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
    assert response.json()["data"] == {"taskId": "script-1", "status": "stopped"}
    assert facade.stopped_scripts == ["script-1"]
    assert facade.stopped_pipelines == []


def test_stop_pipeline_route_delegates_to_pipeline_stop(monkeypatch, tmp_path: Path) -> None:
    facade = FakeControlFacade()
    monkeypatch.setattr(web_app, "get_control_facade", lambda: facade)
    client = _authenticated_client(monkeypatch, tmp_path)

    response = client.post("/api/run/pipeline/pipeline-1/stop", json={})

    assert response.status_code == 200
    assert response.json()["data"] == {"taskId": "pipeline-1", "status": "stopped"}
    assert facade.stopped_scripts == []
    assert facade.stopped_pipelines == ["pipeline-1"]


def test_stop_route_rejects_deleted_task_id(monkeypatch, tmp_path: Path) -> None:
    facade = FakeControlFacade()
    monkeypatch.setattr(web_app, "get_control_facade", lambda: facade)
    client = _authenticated_client(monkeypatch, tmp_path)

    response = client.post("/api/run/script/deleted-task/stop", json={})

    assert response.status_code == 404
    assert response.json()["detail"] == "任务不存在或已删除: deleted-task"
    assert facade.stopped_scripts == []


def test_run_lua_uses_editor_workspace_path(monkeypatch, tmp_path: Path) -> None:
    facade = FakeRunFacade()
    monkeypatch.setattr(web_app, "get_control_facade", lambda: facade)
    monkeypatch.chdir(tmp_path)
    client = _authenticated_client(monkeypatch, tmp_path)

    response = client.post(
        "/api/run/lua",
        json={"scriptPath": "scripts/demo.lua", "luaCode": "return 42"},
    )

    assert response.status_code == 200
    assert facade.run_script_calls == [
        (".mluascript_web/lua/scripts/demo.lua", "return 42", "LOCAL")
    ]


def test_run_lua_allows_unsaved_editor_code(monkeypatch, tmp_path: Path) -> None:
    facade = FakeRunFacade()
    monkeypatch.setattr(web_app, "get_control_facade", lambda: facade)
    monkeypatch.chdir(tmp_path)
    client = _authenticated_client(monkeypatch, tmp_path)

    response = client.post("/api/run/lua", json={"luaCode": "return 42"})

    assert response.status_code == 200
    assert facade.run_script_calls == [
        (".mluascript_web/lua/untitled.lua", "return 42", "LOCAL")
    ]


def test_task_resources_use_builds_instead_of_project_sources(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    source = tmp_path / ".mluascript_web" / "projects" / "demo" / "scripts" / "main.lua"
    build = tmp_path / ".mluascript_web" / "builds" / "demo" / "1111111111111111" / "demo.lua"
    source.parent.mkdir(parents=True)
    build.parent.mkdir(parents=True)
    source.write_text("return 'source'", encoding="utf-8")
    build.write_text("return 'build'", encoding="utf-8")
    client = _authenticated_client(monkeypatch, tmp_path)

    response = client.get("/api/system/scripts")

    assert response.status_code == 200
    items = response.json()["data"]["items"]
    build_items = [item for item in items if item["source"] == "build"]
    assert len(build_items) == 1
    assert build_items[0]["path"].endswith(".mluascript_web/builds/demo/1111111111111111/demo.lua")
    assert not any(".mluascript_web/projects" in item["path"].replace("\\", "/") for item in items)


def test_run_build_artifact_delegates_with_artifact_summary(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    build = tmp_path / ".mluascript_web" / "builds" / "demo" / "1111111111111111" / "demo.lua"
    build.parent.mkdir(parents=True)
    build.write_text("return 42", encoding="utf-8")
    facade = FakeArtifactRunFacade()
    monkeypatch.setattr(web_app, "get_control_facade", lambda: facade)
    client = _authenticated_client(monkeypatch, tmp_path)
    items = client.get("/api/system/scripts").json()["data"]["items"]
    artifact_id = next(item["id"] for item in items if item["source"] == "build")

    response = client.post("/api/run/artifact", json={"artifactId": artifact_id})

    assert response.status_code == 200
    assert response.json()["data"]["taskId"] == "artifact-run-1"
    assert facade.artifact_run_calls[0]["code"] == "return 42"
    assert facade.artifact_run_calls[0]["target"] == "LOCAL"
    assert facade.artifact_run_calls[0]["title"].endswith(".mluascript_web/builds/demo/1111111111111111/demo.lua")
    assert facade.artifact_run_calls[0]["summary"]["artifact_id"] == artifact_id


def test_artifact_readme_route_returns_verified_markdown(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    _write_readme_package(tmp_path / ".mluascript_web" / "builds" / "readme.mlspkg")
    client = _authenticated_client(monkeypatch, tmp_path)
    items = client.get("/api/system/scripts").json()["data"]["items"]
    artifact = next(item for item in items if item["kind"] == "package")

    response = client.get(f"/api/system/scripts/{artifact['id']}/readme")

    assert response.status_code == 200
    assert response.json()["data"]["name"] == "说明包"
    assert response.json()["data"]["markdown"] == "# 说明包\n\n安全说明。\n"


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


def test_save_lua_file_creates_missing_target(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(web_app, "_get_web_config", _test_web_config)
    monkeypatch.chdir(tmp_path)
    client = _authenticated_client(monkeypatch, tmp_path)

    response = client.put(
        "/api/editor/lua/files/content",
        json={
            "path": "scripts/recovered.lua",
            "content": "print('recovered')",
            "expectedMtime": 123.0,
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["path"] == "scripts/recovered.lua"
    recovered = tmp_path / ".mluascript_web" / "lua" / "scripts" / "recovered.lua"
    assert recovered.read_text(encoding="utf-8") == "print('recovered')"


def test_save_lua_file_recreates_file_deleted_after_loading(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(web_app, "_get_web_config", _test_web_config)
    monkeypatch.chdir(tmp_path)
    client = _authenticated_client(monkeypatch, tmp_path)

    created = client.post(
        "/api/editor/lua/files",
        json={"path": "deleted.lua", "content": "print('old')"},
    ).json()["data"]
    target = tmp_path / ".mluascript_web" / "lua" / "deleted.lua"
    target.unlink()

    response = client.put(
        "/api/editor/lua/files/content",
        json={
            "path": "deleted.lua",
            "content": "print('new')",
            "expectedMtime": created["mtime"],
        },
    )

    assert response.status_code == 200
    assert target.read_text(encoding="utf-8") == "print('new')"


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
