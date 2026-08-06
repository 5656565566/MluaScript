from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from mluascript.frontends.web import app as web_app


def _web_config(project_root: Path) -> SimpleNamespace:
    return SimpleNamespace(
        username="admin",
        password="secret-pass",
        session_secret="0123456789abcdef",
        session_max_age_seconds=3600,
        project_roots=[str(project_root)],
    )


def _client(monkeypatch, tmp_path: Path) -> TestClient:
    monkeypatch.setattr(web_app, "_get_web_config", lambda: _web_config(tmp_path / "projects"))
    client = TestClient(web_app.create_web_app(tmp_path / "dist"))
    response = client.post("/api/auth/login", json={"username": "admin", "password": "secret-pass"})
    assert response.status_code == 200
    return client


def test_project_routes_create_open_save_validate_build_and_download(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)

    created_response = client.post(
        "/api/projects",
        json={
            "name": "Demo",
            "packageId": "com.example.demo",
            "author": "Demo Author",
            "description": "Demo description",
            "directory": "demo",
            "template": "blank-blockly",
        },
    )
    assert created_response.status_code == 200
    project = created_response.json()["data"]

    updated_response = client.patch(
        f"/api/projects/{project['key']}",
        json={
            "name": "Renamed Demo",
            "packageId": "com.example.renamed",
            "version": "1.2.0",
            "author": "Renamed Author",
            "description": "Renamed description",
        },
    )
    assert updated_response.status_code == 200
    assert updated_response.json()["data"]["name"] == "Renamed Demo"
    assert updated_response.json()["data"]["author"] == "Renamed Author"
    assert updated_response.json()["data"]["description"] == "Renamed description"

    listed = client.get("/api/projects")
    assert listed.status_code == 200
    assert listed.json()["data"]["items"][0]["key"] == project["key"]

    opened = client.post(f"/api/projects/{project['key']}:open", json={})
    assert opened.status_code == 200
    assert opened.json()["data"]["manifest"]["package"]["id"] == "com.example.renamed"
    assert opened.json()["data"]["manifest"]["package"]["author"] == "Renamed Author"

    file_data = client.get(
        f"/api/projects/{project['key']}/files/content",
        params={"path": "blockly/main.xml"},
    ).json()["data"]
    saved = client.put(
        f"/api/projects/{project['key']}/files/content",
        json={
            "path": "blockly/main.xml",
            "content": '<xml xmlns="https://developers.google.com/blockly/xml"></xml>\n',
            "expectedMtime": file_data["mtime"],
        },
    )
    assert saved.status_code == 200

    validation = client.post(f"/api/projects/{project['key']}/validate", json={})
    assert validation.status_code == 200
    assert validation.json()["data"]["valid"] is True

    build = client.post(
        f"/api/projects/{project['key']}/build",
        json={"generatedLua": "print('from blockly')\n", "generatedFrom": "blockly/main.xml"},
    )
    assert build.status_code == 200
    build_data = build.json()["data"]
    download = client.get(build_data["downloadPath"])
    assert download.status_code == 200
    assert build_data["filename"] in download.headers["content-disposition"]
    assert download.content.startswith(b"PK")


def test_project_routes_require_authentication(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(web_app, "_get_web_config", lambda: _web_config(tmp_path / "projects"))
    client = TestClient(web_app.create_web_app(tmp_path / "dist"))

    response = client.get("/api/projects")

    assert response.status_code == 401


def test_project_route_renames_manifest_entrypoint_and_updates_project_metadata(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)
    project = client.post(
        "/api/projects",
        json={"name": "Lua Rename", "packageId": "com.example.lua-rename", "directory": "lua-rename"},
    ).json()["data"]

    renamed = client.patch(
        f"/api/projects/{project['key']}/tree",
        json={"path": "scripts/main.lua", "newName": "entry.lua"},
    )
    opened = client.post(f"/api/projects/{project['key']}:open", json={})
    old_file = client.get(
        f"/api/projects/{project['key']}/files/content",
        params={"path": "scripts/main.lua"},
    )
    new_file = client.get(
        f"/api/projects/{project['key']}/files/content",
        params={"path": "scripts/entry.lua"},
    )

    assert renamed.status_code == 200
    assert renamed.json()["data"]["path"] == "scripts/entry.lua"
    assert opened.json()["data"]["project"]["primary_path"] == "scripts/entry.lua"
    assert opened.json()["data"]["manifest"]["entrypoints"]["main"]["script"] == "scripts/entry.lua"
    assert old_file.status_code == 400
    assert new_file.status_code == 200


def test_project_debug_route_passes_memory_sources_and_debug_metadata(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)
    project = client.post(
        "/api/projects",
        json={"name": "Debug", "packageId": "com.example.debug", "directory": "debug"},
    ).json()["data"]
    calls: list[dict[str, object]] = []

    class FakeFacade:
        def get_device_overview(self):
            return SimpleNamespace(connection=SimpleNamespace(label="ADB:fallback"))

        def run_script(self, script_path, code, target, **kwargs):
            calls.append({"script_path": script_path, "code": code, "target": target, **kwargs})
            return "debug-task-id"

    monkeypatch.setattr(web_app, "get_control_facade", lambda: FakeFacade())
    response = client.post(
        f"/api/projects/{project['key']}/debug",
        json={
            "mode": "script",
            "sessionLabel": "ADB:selected",
            "entryPath": "scripts/main.lua",
            "luaCode": "return require('lib/helper')",
            "sourceOverrides": {
                "scripts/main.lua": "return require('lib/helper')",
                "scripts/lib/helper.lua": "return 42",
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["taskId"] == "debug-task-id"
    assert calls[0]["target"] == "ADB:selected"
    assert calls[0]["source_overrides"]["scripts/lib/helper.lua"] == "return 42"
    assert calls[0]["summary"] == {
        "debug": True,
        "project_key": project["key"],
        "entry_path": "scripts/main.lua",
        "debug_mode": "script",
    }


def test_project_task_template_debug_uses_private_web_config(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)
    project = client.post(
        "/api/projects",
        json={"name": "Template Debug", "packageId": "com.example.template", "directory": "template-debug"},
    ).json()["data"]
    source = "\n".join(
        [
            "-- @mlua-template:start",
            '-- {"mode":"task","vars":{"value":{"tp":"int","def":1}},"tasks":[{"k":"single","fn":"run_single","args":["value"]}]}',
            "-- @mlua-template:end",
            "function run_single(args) return args.value end",
        ]
    )
    current = client.get(
        f"/api/projects/{project['key']}/files/content",
        params={"path": "scripts/main.lua"},
    ).json()["data"]
    client.put(
        f"/api/projects/{project['key']}/files/content",
        json={"path": "scripts/main.lua", "content": source, "expectedMtime": current["mtime"]},
    )
    readme_file = client.get(
        f"/api/projects/{project['key']}/files/content",
        params={"path": "README.md"},
    ).json()["data"]
    client.put(
        f"/api/projects/{project['key']}/files/content",
        json={"path": "README.md", "content": "# 模板说明\n", "expectedMtime": readme_file["mtime"]},
    )
    calls: list[str] = []

    class FakeFacade:
        def get_device_overview(self):
            return SimpleNamespace(connection=SimpleNamespace(label="LOCAL"))

        def run_script(self, _script_path, code, _target, **_kwargs):
            calls.append(code)
            return "template-task-id"

    monkeypatch.setattr(web_app, "get_control_facade", lambda: FakeFacade())
    template = client.get(
        f"/api/projects/{project['key']}/template",
        params={"path": "scripts/main.lua"},
    )
    started = client.post(
        f"/api/projects/{project['key']}/debug",
        json={
            "mode": "template",
            "entryPath": "scripts/main.lua",
            "luaCode": source,
            "templateMode": "task",
            "runtime": {"selectedTaskKey": "single", "tasks": {"single": {"value": 7}}},
        },
    )

    assert template.status_code == 200
    assert template.json()["data"]["hasTemplate"] is True
    assert template.json()["data"]["readme"]["markdown"] == "# 模板说明\n"
    assert started.status_code == 200
    assert "run_single" in calls[0]
    assert "value = 7" in calls[0]
    config_path = Path(template.json()["data"]["configPath"])
    assert config_path.parent == tmp_path / "settings" / "templates" / project["key"]


def test_project_routes_create_directory_file_and_stream_binary(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)
    created = client.post(
        "/api/projects",
        json={"name": "Editor", "packageId": "com.example.editor", "directory": "editor"},
    ).json()["data"]
    project_key = created["key"]

    directory = client.post(
        f"/api/projects/{project_key}/directories",
        json={"path": "resources/assets/images"},
    )
    text_file = client.post(
        f"/api/projects/{project_key}/files",
        json={"path": "scripts/tasks/new.lua", "content": "return true\n"},
    )
    uploaded = client.put(
        f"/api/projects/{project_key}/files/binary",
        params={"path": "resources/assets/images/model.bin"},
        content=b"\x00\x01model-data",
        headers={"content-type": "application/octet-stream"},
    )
    binary_metadata = client.get(
        f"/api/projects/{project_key}/files/content",
        params={"path": "resources/assets/images/model.bin"},
    ).json()["data"]
    downloaded = client.get(
        f"/api/projects/{project_key}/files/raw",
        params={"path": "resources/assets/images/model.bin"},
    )
    renamed = client.patch(
        f"/api/projects/{project_key}/tree",
        json={"path": "scripts/tasks/new.lua", "newName": "renamed.lua"},
    )
    moved = client.patch(
        f"/api/projects/{project_key}/tree:move",
        json={"sourcePath": "scripts/tasks/renamed.lua", "destinationPath": "resources/assets/renamed.lua"},
    )

    assert directory.status_code == 200
    assert text_file.status_code == 200
    assert text_file.json()["data"]["content"] == "return true\n"
    assert uploaded.status_code == 200
    assert binary_metadata["encoding"] is None
    assert "contentBase64" not in binary_metadata
    assert downloaded.content == b"\x00\x01model-data"
    assert renamed.status_code == 200
    assert renamed.json()["data"]["path"] == "scripts/tasks/renamed.lua"
    assert moved.status_code == 200
    assert moved.json()["data"]["path"] == "resources/assets/renamed.lua"
    old_path = client.get(
        f"/api/projects/{project_key}/files/content",
        params={"path": "scripts/tasks/renamed.lua"},
    )
    new_path = client.get(
        f"/api/projects/{project_key}/files/content",
        params={"path": "resources/assets/renamed.lua"},
    )
    assert old_path.status_code == 400
    assert new_path.status_code == 200
    deleted = client.delete(
        f"/api/projects/{project_key}/files",
        params={"path": "resources/assets/renamed.lua"},
    )
    assert deleted.status_code == 200
    assert deleted.json()["data"]["path"] == "resources/assets/renamed.lua"
    assert new_path.json()["data"]["content"] == "return true\n"
