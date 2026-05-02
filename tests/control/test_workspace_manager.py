from __future__ import annotations

from pathlib import Path

from mluascript.control.workspace.manager import WorkspaceManager


def test_resolve_project_uses_script_parent_as_project_root(tmp_path: Path) -> None:
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    script_file = project_dir / "test.lua"
    script_file.write_text("print('hello')", encoding="utf-8")
    (project_dir / "hero.png").write_text("fake", encoding="utf-8")

    manager = WorkspaceManager(tmp_path)
    project = manager.resolve_project("demo/test.lua")

    assert project.name == "demo"
    assert Path(project.root_dir) == project_dir.resolve()
    assert Path(project.resource_dir) == project_dir.resolve()


def test_build_script_run_locator_collects_same_directory_resources(tmp_path: Path) -> None:
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    script_file = project_dir / "test.lua"
    script_file.write_text("print('hello')", encoding="utf-8")
    image_file = project_dir / "xxx.png"
    image_file.write_text("fake-image", encoding="utf-8")
    json_file = project_dir / "nodes.json"
    json_file.write_text("{}", encoding="utf-8")

    manager = WorkspaceManager(tmp_path)
    locator = manager.build_script_run_locator("demo/test.lua")

    assert Path(locator.script_file) == script_file.resolve()
    assert Path(locator.script_dir) == project_dir.resolve()
    assert Path(locator.resource_dir) == project_dir.resolve()
    assert {asset.relative_path for asset in locator.resources} == {"xxx.png", "nodes.json"}
    assert {asset.kind for asset in locator.resources} == {"image", "data"}


def test_build_pipeline_run_locator_prefers_resource_directory_when_present(tmp_path: Path) -> None:
    project_dir = tmp_path / "demo"
    resource_dir = project_dir / "resource"
    project_dir.mkdir()
    resource_dir.mkdir()
    script_file = project_dir / "test.lua"
    script_file.write_text("print('hello')", encoding="utf-8")
    resource_file = resource_dir / "map.png"
    resource_file.write_text("fake-image", encoding="utf-8")

    manager = WorkspaceManager(tmp_path)
    locator = manager.build_pipeline_run_locator("demo/test.lua")

    assert Path(locator.project_root) == project_dir.resolve()
    assert Path(locator.resource_dir) == resource_dir.resolve()
    assert [asset.relative_path for asset in locator.resources] == ["resource/map.png"]



def test_list_scripts_includes_default_mluascript_web_lua_directory(tmp_path: Path) -> None:
    web_lua_dir = tmp_path / ".mluascript_web" / "lua"
    web_lua_dir.mkdir(parents=True)
    script_file = web_lua_dir / "debug.lua"
    script_file.write_text("print('debug')", encoding="utf-8")

    manager = WorkspaceManager(tmp_path)
    scripts = manager.list_scripts()

    assert [item.path for item in scripts] == [".mluascript_web/lua/debug.lua"]
