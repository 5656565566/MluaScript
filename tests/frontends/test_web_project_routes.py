from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import base64

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

    template_source = "\n".join(
        [
            "-- @mlua-template:start",
            '-- {"mode":"task","vars":{"value":{"tp":"int","def":1}},"tasks":[{"k":"single","fn":"run_single","args":["value"]}]}',
            "-- @mlua-template:end",
            "function run_single(args) return args.value end",
        ]
    )
    preview = client.post(
        f"/api/projects/{project['key']}/template:preview",
        json={
            "entryPath": "scripts/main.lua",
            "luaCode": template_source,
            "sourceOverrides": {"scripts/main.lua": template_source},
        },
    )
    assert preview.status_code == 200
    assert preview.json()["data"]["hasTemplate"] is True


def test_device_items_payload_returns_all_discovered_desktop_windows(monkeypatch) -> None:
    class FakeDeviceFacade:
        _desktop_raw = [
            {"handle": index + 1, "window_name": f"Window {index + 1}", "platform": "windows"}
            for index in range(36)
        ]

    class FakeFacade:
        device_facade = FakeDeviceFacade()

        @staticmethod
        def get_device_overview():
            empty_page = SimpleNamespace(items=[])
            return SimpleNamespace(adb=empty_page, emulator=empty_page, browser=empty_page)

    monkeypatch.setattr(web_app, "get_control_facade", lambda: FakeFacade())

    items = web_app._build_device_items_payload()

    assert len(items) == 36
    assert items[0]["id"] == "desktop:0"
    assert items[-1]["id"] == "desktop:35"
    assert items[-1]["handle"] == 36


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
    assert downloaded.headers["content-disposition"].startswith("attachment")

    image_upload = client.put(
        f"/api/projects/{project_key}/files/binary",
        params={"path": "resources/assets/images/preview.png"},
        content=b"png-data",
        headers={"content-type": "image/png"},
    )
    image_download = client.get(
        f"/api/projects/{project_key}/files/raw",
        params={"path": "resources/assets/images/preview.png"},
    )
    assert image_upload.status_code == 200
    assert image_download.headers["content-type"].startswith("image/png")
    assert image_download.headers["content-disposition"].startswith("inline")
    assert image_download.content == b"png-data"

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


def test_project_image_recognition_route_runs_ocr_with_uploaded_image(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)
    project = client.post(
        "/api/projects",
        json={"name": "Vision", "packageId": "com.example.vision", "directory": "vision"},
    ).json()["data"]
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    context = SimpleNamespace(tasker=object())
    facade = SimpleNamespace(device_facade=SimpleNamespace(_maa_facade=SimpleNamespace(context=context)))
    calls = []
    monkeypatch.setattr(web_app, "get_control_facade", lambda: facade)
    monkeypatch.setattr(web_app, "initialize_maa_runtime", lambda value: value)
    monkeypatch.setattr(
        web_app,
        "find_ocr",
        lambda _context, entry, **kwargs: calls.append((entry, kwargs)) or {"hit": True, "text": "确认"},
    )

    response = client.post(
        f"/api/projects/{project['key']}/recognize-image",
        json={
            "kind": "ocr",
            "imageBase64": base64.b64encode(png).decode("ascii"),
            "expected": "确认|取消",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["result"]["hit"] is True
    assert calls[0][1]["expected"] == ["确认", "取消"]


def test_recognition_resource_alias_resolves_manifest_resource_key(monkeypatch, tmp_path: Path) -> None:
    client = _client(monkeypatch, tmp_path)
    project = client.post(
        "/api/projects",
        json={"name": "Aliases", "packageId": "com.example.aliases", "directory": "aliases"},
    ).json()["data"]
    client.post(
        f"/api/projects/{project['key']}/directories",
        json={"path": "resources/assets/image"},
    )
    uploaded = client.put(
        f"/api/projects/{project['key']}/files/binary",
        params={"path": "resources/assets/image/template.png"},
        content=b"template",
        headers={"content-type": "image/png"},
    )

    resolved = web_app._recognition_resource_path(
        client.app.state.project_service,
        project["key"],
        "assets:image/template.png",
        "模板图片",
    )

    assert uploaded.status_code == 200
    assert Path(resolved).as_posix().endswith("resources/assets/image/template.png")
