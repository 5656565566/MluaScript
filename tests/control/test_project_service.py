from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from mluascript.control.workspace.project_service import ProjectService, ProjectServiceError
from mluascript.control.workspace.module_paths import (
    blockly_source_to_module_key,
    blockly_source_to_script_path,
    script_path_to_module_key,
)


def test_create_open_and_build_project_is_deterministic(tmp_path: Path) -> None:
    service = ProjectService([tmp_path / "projects"], tmp_path / "builds")

    project = service.create_project(
        name="每日任务",
        package_id="com.example.daily-task",
        directory="daily-task",
        template="maa",
    )

    assert project.valid is True
    assert project.entrypoints == ["main"]
    opened = service.open_project(project.key)
    assert opened["manifest"]["schema"] == "mluascript.package/v1"
    assert opened["manifest"]["type"] == "maa"
    assert any(item["path"] == "tasks/main.json" for item in opened["tree"])
    assert not any(item["path"].endswith(".lua") for item in opened["tree"])

    first = service.build(project.key)
    second = service.build(project.key)
    first_bytes = Path(first.artifact_path).read_bytes()
    second_bytes = Path(second.artifact_path).read_bytes()
    assert first_bytes == second_bytes
    assert first.sha256 == second.sha256

    with zipfile.ZipFile(first.artifact_path) as archive:
        names = archive.namelist()
        assert names == sorted(names)
        assert "mluascript.yaml" in names
        assert "META-INF/files.sha256" in names
        checksum_text = archive.read("META-INF/files.sha256").decode("utf-8")
        assert "tasks/main.json" in checksum_text


def test_project_file_write_uses_mtime_conflict_detection(tmp_path: Path) -> None:
    service = ProjectService([tmp_path / "projects"], tmp_path / "builds")
    project = service.create_project(name="Demo", package_id="com.example.demo")

    original = service.read_file(project.key, "scripts/main.lua")
    updated = service.write_file(project.key, "scripts/main.lua", "print('updated')\n", original.mtime)
    assert updated.content == "print('updated')\n"

    with pytest.raises(ProjectServiceError, match="发生变化"):
        service.write_file(project.key, "scripts/main.lua", "print('stale')\n", original.mtime)


def test_project_metadata_update_preserves_directory_and_updates_manifest(tmp_path: Path) -> None:
    service = ProjectService([tmp_path / "projects"], tmp_path / "builds")
    project = service.create_project(
        name="Before",
        package_id="com.example.before",
        author="Before Author",
        description="Before description",
        directory="stable-directory",
    )

    updated = service.update_project(
        project.key,
        name="After",
        package_id="com.example.after",
        version="2.0.0",
        author="After Author",
        description="After description",
    )
    opened = service.open_project(project.key)

    assert updated.key == project.key
    assert updated.directory == "stable-directory"
    assert updated.name == "After"
    assert updated.package_id == "com.example.after"
    assert updated.version == "2.0.0"
    assert updated.author == "After Author"
    assert updated.description == "After description"
    assert opened["manifest"]["package"] == {
        "author": "After Author",
        "description": "After description",
        "id": "com.example.after",
        "name": "After",
        "version": "2.0.0",
    }


def test_project_rejects_traversal_and_reports_missing_model(tmp_path: Path) -> None:
    service = ProjectService([tmp_path / "projects"], tmp_path / "builds")
    project = service.create_project(name="Demo", package_id="com.example.demo")

    with pytest.raises(ProjectServiceError, match="路径穿越"):
        service.read_file(project.key, "../outside.txt")

    manifest_path = tmp_path / "projects" / "Demo" / "mluascript.yaml"
    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8").replace("models: {}", "models:\n  detector:\n    type: maa.nnd\n    path: models/nnd/detector/model.onnx"),
        encoding="utf-8",
    )
    diagnostics = service.validate(project.key)
    assert any(item.code == "path.invalid" and "model detector" in item.message for item in diagnostics)


def test_declared_model_is_included_in_package(tmp_path: Path) -> None:
    service = ProjectService([tmp_path / "projects"], tmp_path / "builds")
    project = service.create_project(name="Model Demo", package_id="com.example.model")
    project_root = tmp_path / "projects" / "Model-Demo"
    model_file = project_root / "models" / "nnd" / "detector" / "model.onnx"
    model_file.parent.mkdir(parents=True)
    model_file.write_bytes(b"fake-onnx")
    manifest_path = project_root / "mluascript.yaml"
    manifest = manifest_path.read_text(encoding="utf-8")
    manifest = manifest.replace("models: {}", "models:\n  detector:\n    type: maa.nnd\n    path: models/nnd/detector/model.onnx")
    manifest_path.write_bytes(manifest.encode("utf-8"))

    result = service.build(project.key)

    with zipfile.ZipFile(result.artifact_path) as archive:
        assert archive.read("models/nnd/detector/model.onnx") == b"fake-onnx"
    assert result.model_count == 1


def test_project_file_management_keeps_binary_content_out_of_json(tmp_path: Path) -> None:
    service = ProjectService([tmp_path / "projects"], tmp_path / "builds")
    project = service.create_project(name="Editor Demo", package_id="com.example.editor")

    directory = service.create_directory(project.key, "resources/assets/images")
    text_file = service.create_file(project.key, "scripts/tasks/new.lua", "return true\n")
    with service.open_binary_writer(project.key, "resources/assets/images/sample.bin") as (stream, path):
        stream.write(b"\x00\x01binary")

    binary_file = service.read_file(project.key, path)

    assert directory.kind == "directory"
    assert text_file.content == "return true\n"
    assert binary_file.encoding is None
    assert binary_file.content is None
    assert binary_file.content is None
    assert binary_file.size == 8


def test_create_nested_project_and_reject_empty_version(tmp_path: Path) -> None:
    service = ProjectService([tmp_path / "projects"], tmp_path / "builds")

    project = service.create_project(
        name="Nested Demo",
        package_id="com.example.nested",
        directory="team/nested-demo",
    )

    assert project.directory == "team/nested-demo"
    with pytest.raises(ProjectServiceError, match="版本不能为空"):
        service.create_project(name="Invalid", package_id="com.example.invalid", version="")


def test_project_templates_create_distinct_package_entrypoints(tmp_path: Path) -> None:
    service = ProjectService([tmp_path / "projects"], tmp_path / "builds")

    lua_project = service.create_project(name="Lua", package_id="com.example.lua", template="lua-package")
    blockly_project = service.create_project(
        name="Blockly",
        package_id="com.example.blockly",
        template="blockly-package",
    )
    maa_project = service.create_project(name="Maa", package_id="com.example.maa", template="maa")

    lua_opened = service.open_project(lua_project.key)
    blockly_opened = service.open_project(blockly_project.key)
    maa_opened = service.open_project(maa_project.key)
    assert "blockly" not in lua_opened["manifest"]["entrypoints"]["main"]
    assert not (tmp_path / "projects" / "Lua" / "blockly" / "main.xml").exists()
    assert blockly_opened["manifest"]["entrypoints"]["main"]["blockly"] == "blockly/main.xml"
    assert (tmp_path / "projects" / "Blockly" / "blockly" / "main.xml").is_file()
    assert (tmp_path / "projects" / "Blockly" / "blockly" / "lib").is_dir()
    assert (tmp_path / "projects" / "Blockly" / "scripts" / "lib").is_dir()
    assert not (tmp_path / "projects" / "Blockly" / "scripts" / "main.lua").exists()
    assert maa_opened["manifest"]["capabilities"]["device"] is True
    assert maa_opened["manifest"]["entrypoints"]["main"]["maa"] == "tasks/main.json"
    assert service.prepare_pipeline_debug_target(maa_project.key).entry == "main"
    assert not (tmp_path / "projects" / "Maa" / "scripts").exists()


def test_project_debug_target_maps_blockly_modules_to_virtual_scripts(tmp_path: Path) -> None:
    service = ProjectService([tmp_path / "projects"], tmp_path / "builds")
    project = service.create_project(name="Blockly Debug", package_id="com.example.debug", template="blockly-package")

    target = service.prepare_debug_target(
        project.key,
        source_overrides={
            "scripts/main.lua": "return require('lib/math')\n",
            "scripts/lib/math.lua": "return 42\n",
        },
    )

    assert target.entry_path == "scripts/main.lua"
    assert target.source_overrides["scripts/lib/math.lua"] == "return 42\n"
    with pytest.raises(ProjectServiceError, match="仅允许 scripts"):
        service.prepare_debug_target(project.key, source_overrides={"resources/debug.lua": "return 1"})
    with pytest.raises(ProjectServiceError, match="路径穿越"):
        service.prepare_debug_target(project.key, entry_path="../outside.lua")


def test_maa_debug_descriptor_validates_entry_and_location(tmp_path: Path) -> None:
    service = ProjectService([tmp_path / "projects"], tmp_path / "builds")
    project = service.create_project(name="Maa Debug", package_id="com.example.maa-debug", template="maa")
    descriptor = tmp_path / "projects" / "Maa-Debug" / "tasks" / "main.json"
    descriptor.write_text('{"entry":"PipelineEntry","override":{"node":{"retry":2}}}\n', encoding="utf-8")

    target = service.prepare_pipeline_debug_target(project.key)

    assert target.entry == "PipelineEntry"
    assert target.override == {"node": {"retry": 2}}
    with pytest.raises(ProjectServiceError, match="tasks"):
        service.prepare_pipeline_debug_target(project.key, descriptor_path="resources/maa/main.json")
    descriptor.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ProjectServiceError, match="缺少 entry"):
        service.prepare_pipeline_debug_target(project.key)


def test_single_file_projects_use_named_folders_and_export_lua(tmp_path: Path) -> None:
    service = ProjectService([tmp_path / "projects"], tmp_path / "builds")

    lua_project = service.create_project(name="Lua Demo.lua", package_id="", template="lua-file")
    blockly_project = service.create_project(name="流程示例.xml", package_id="", template="blockly-file")

    lua_source = tmp_path / "projects" / "Lua-Demo" / "Lua-Demo.lua"
    blockly_source = tmp_path / "projects" / "流程示例" / "流程示例.xml"
    assert lua_source.is_file()
    assert blockly_source.is_file()
    assert lua_project.project_type == "lua-file"
    assert blockly_project.project_type == "blockly-file"
    assert blockly_project.primary_path == "流程示例.xml"

    lua_build = service.build(lua_project.key)
    blockly_build = service.build(
        blockly_project.key,
        generated_lua="print('generated')\n",
        generated_from="流程示例.xml",
    )
    assert Path(lua_build.artifact_path).suffix == ".lua"
    assert Path(blockly_build.artifact_path).read_text(encoding="utf-8") == "print('generated')\n"
    with pytest.raises(ProjectServiceError, match="单文件项目不支持"):
        service.create_file(blockly_project.key, "extra.lua")


def test_blockly_package_writes_generated_lua_only_into_archive(tmp_path: Path) -> None:
    service = ProjectService([tmp_path / "projects"], tmp_path / "builds")
    project = service.create_project(name="Blockly", package_id="com.example.blockly", template="blockly-package")

    result = service.build(
        project.key,
        generated_lua="print('generated')\n",
        generated_from="blockly/main.xml",
    )

    assert not (tmp_path / "projects" / "Blockly" / "scripts" / "main.lua").exists()
    with zipfile.ZipFile(result.artifact_path) as archive:
        assert archive.read("scripts/main.lua") == b"print('generated')\n"
        manifest = archive.read("mluascript.yaml").decode("utf-8")
        assert "script: scripts/main.lua" in manifest


def test_project_tree_renames_custom_and_manifest_files_while_protecting_structure(tmp_path: Path) -> None:
    service = ProjectService([tmp_path / "projects"], tmp_path / "builds")
    project = service.create_project(name="Rename", package_id="com.example.rename")
    service.create_file(project.key, "scripts/tasks/custom.lua", "return true\n")

    renamed = service.rename_path(project.key, "scripts/tasks/custom.lua", "daily.lua")

    assert renamed.path == "scripts/tasks/daily.lua"
    assert service.read_file(project.key, renamed.path).content == "return true\n"
    entrypoint = service.rename_path(project.key, "scripts/main.lua", "entry.lua")

    assert entrypoint.path == "scripts/entry.lua"
    opened = service.open_project(project.key)
    assert opened["manifest"]["entrypoints"]["main"]["script"] == "scripts/entry.lua"
    assert opened["project"]["primary_path"] == "scripts/entry.lua"
    assert service.read_file(project.key, "scripts/entry.lua").content
    with pytest.raises(ProjectServiceError, match="manifest 管理"):
        service.rename_path(project.key, "scripts", "source")
    with pytest.raises(ProjectServiceError, match="manifest 管理"):
        service.rename_path(project.key, "mluascript.yaml", "project.yaml")
    with pytest.raises(ProjectServiceError, match="普通文件名"):
        service.rename_path(project.key, renamed.path, "invalid?.lua")


def test_project_tree_moves_custom_files_and_directories_safely(tmp_path: Path) -> None:
    service = ProjectService([tmp_path / "projects"], tmp_path / "builds")
    project = service.create_project(name="Move", package_id="com.example.move")
    service.create_directory(project.key, "custom")
    service.create_directory(project.key, "custom/nested")
    service.create_file(project.key, "custom/nested/task.lua", "return true\n")
    service.create_directory(project.key, "destination")

    moved_file = service.move_path(project.key, "custom/nested/task.lua", "destination/task.lua")
    moved_directory = service.move_path(project.key, "custom/nested", "destination/nested")

    assert moved_file.path == "destination/task.lua"
    assert moved_directory.path == "destination/nested"
    assert service.read_file(project.key, "destination/task.lua").content == "return true\n"
    with pytest.raises(ProjectServiceError, match="已存在"):
        service.move_path(project.key, "destination/task.lua", "scripts/main.lua")
    service.create_directory(project.key, "custom/child")
    with pytest.raises(ProjectServiceError, match="自身或其子目录"):
        service.move_path(project.key, "custom", "custom/child/custom")
    with pytest.raises(ProjectServiceError, match="manifest 管理"):
        service.move_path(project.key, "scripts/main.lua", "destination/main.lua")


def test_project_tree_move_is_disabled_for_single_file_projects(tmp_path: Path) -> None:
    service = ProjectService([tmp_path / "projects"], tmp_path / "builds")
    project = service.create_project(
        name="Single",
        package_id="",
        directory="single",
        template="lua-file",
    )

    with pytest.raises(ProjectServiceError, match="单文件项目不支持"):
        service.move_path(project.key, "single.lua", "renamed.lua")


def test_project_tree_deletes_only_custom_files(tmp_path: Path) -> None:
    service = ProjectService([tmp_path / "projects"], tmp_path / "builds")
    project = service.create_project(name="Delete", package_id="com.example.delete")
    service.create_file(project.key, "scripts/lib/custom.lua", "return true\n")

    deleted = service.delete_file(project.key, "scripts/lib/custom.lua")

    assert deleted == "scripts/lib/custom.lua"
    assert not (tmp_path / "projects" / "Delete" / "scripts" / "lib" / "custom.lua").exists()
    with pytest.raises(ProjectServiceError, match="manifest 管理"):
        service.delete_file(project.key, "scripts/main.lua")
    with pytest.raises(ProjectServiceError, match="只能删除文件"):
        service.delete_file(project.key, "scripts/lib")


def test_blockly_module_paths_preserve_relative_directories() -> None:
    assert blockly_source_to_script_path("blockly/lib/math.xml") == "scripts/lib/math.lua"
    assert blockly_source_to_module_key("blockly/lib/math.xml") == "lib/math"
    assert script_path_to_module_key("scripts/lib/math.lua") == "lib/math"

    with pytest.raises(ValueError, match="blockly/"):
        blockly_source_to_script_path("resources/math.xml")
    with pytest.raises(ValueError, match="scripts/"):
        script_path_to_module_key("lib/math.lua")


def test_blockly_project_validates_generated_lua_collisions(tmp_path: Path) -> None:
    service = ProjectService([tmp_path / "projects"], tmp_path / "builds")
    project = service.create_project(name="Blockly", package_id="com.example.blockly", template="blockly-package")
    project_root = tmp_path / "projects" / "Blockly"
    generated_target = project_root / "scripts" / "main.lua"
    generated_target.parent.mkdir(parents=True, exist_ok=True)
    generated_target.write_text("return {}\n", encoding="utf-8")

    diagnostics = service.validate(project.key)

    assert any(item.code == "blockly.script_collision" and item.path == "scripts/main.lua" for item in diagnostics)


def test_only_blockly_package_accepts_blockly_source_tree(tmp_path: Path) -> None:
    service = ProjectService([tmp_path / "projects"], tmp_path / "builds")
    lua_project = service.create_project(name="Lua", package_id="com.example.lua", template="lua-package")
    maa_project = service.create_project(name="Maa", package_id="com.example.maa", template="maa")
    blockly_project = service.create_project(name="Blockly", package_id="com.example.blockly", template="blockly-package")

    with pytest.raises(ProjectServiceError, match="不支持 Blockly"):
        service.create_directory(lua_project.key, "blockly")
    with pytest.raises(ProjectServiceError, match="不支持 Blockly"):
        service.create_file(maa_project.key, "blockly/extra.xml", "<xml />")

    created = service.create_file(blockly_project.key, "blockly/lib/math.xml", "<xml />")
    assert created.path == "blockly/lib/math.xml"
    with pytest.raises(ProjectServiceError, match="生成目标冲突"):
        service.create_file(blockly_project.key, "scripts/lib/math.lua", "return {}\n")


def test_blockly_package_builds_every_xml_to_mirrored_script_path(tmp_path: Path) -> None:
    service = ProjectService([tmp_path / "projects"], tmp_path / "builds")
    project = service.create_project(name="Blockly", package_id="com.example.blockly", template="blockly-package")
    service.create_file(project.key, "blockly/lib/math.xml", "<xml />")

    with pytest.raises(ProjectServiceError, match="缺少生成结果"):
        service.build(
            project.key,
            generated_modules={"blockly/main.xml": "print('main')\n"},
        )

    result = service.build(
        project.key,
        generated_modules={
            "blockly/main.xml": "local math = require('lib/math')\n",
            "blockly/lib/math.xml": "return { add = add }\n",
        },
    )

    with zipfile.ZipFile(result.artifact_path) as archive:
        assert archive.read("scripts/main.lua") == b"local math = require('lib/math')\n"
        assert archive.read("scripts/lib/math.lua") == b"return { add = add }\n"
        assert "script: scripts/main.lua" in archive.read("mluascript.yaml").decode("utf-8")


def test_project_module_index_extracts_blockly_and_lua_exports(tmp_path: Path) -> None:
    service = ProjectService([tmp_path / "projects"], tmp_path / "builds")
    project = service.create_project(name="Blockly", package_id="com.example.blockly", template="blockly-package")
    blockly_source = '''<xml xmlns="https://developers.google.com/blockly/xml">
      <block type="procedures_defreturn"><mutation><arg name="a"/><arg name="b"/></mutation><field name="NAME">add</field></block>
      <block type="lua_module_export_function"><field name="FUNC_VALUES">["add"]</field></block>
    </xml>'''
    service.write_file(project.key, "blockly/main.xml", blockly_source)
    service.create_file(
        project.key,
        "scripts/helper.lua",
        "local function greet(name) return name end\nreturn { greet = greet }\n",
    )

    modules = service.get_module_index(project.key)

    assert modules == [
        {
            "key": "helper",
            "source": "scripts/helper.lua",
            "kind": "lua",
            "exports": [{"name": "greet", "params": ["name"], "hasReturn": True, "returnKind": "value", "callStyle": "function"}],
        },
        {
            "key": "main",
            "source": "blockly/main.xml",
            "kind": "blockly",
            "exports": [{"name": "add", "params": ["a", "b"], "hasReturn": True, "returnKind": "value", "callStyle": "function"}],
        },
    ]


def test_lua_module_index_analyzes_standard_function_forms_and_returns(tmp_path: Path) -> None:
    service = ProjectService([tmp_path / "projects"], tmp_path / "builds")
    project = service.create_project(name="Lua", package_id="com.example.lua", template="lua-package")
    service.create_file(
        project.key,
        "scripts/lib/tools.lua",
        """
local function notify_user(message)
    print(message)
end

local format_name = function(name, prefix)
    return prefix .. name
end

return {
    notify = notify_user,
    format = format_name,
}
""",
    )

    module = next(item for item in service.get_module_index(project.key) if item["key"] == "lib/tools")

    assert module["kind"] == "lua"
    assert module["exports"] == [
        {"name": "notify", "params": ["message"], "hasReturn": False, "returnKind": "none", "callStyle": "function"},
        {"name": "format", "params": ["name", "prefix"], "hasReturn": True, "returnKind": "value", "callStyle": "function"},
    ]


def test_lua_module_index_extracts_module_table_exports(tmp_path: Path) -> None:
    service = ProjectService([tmp_path / "projects"], tmp_path / "builds")
    project = service.create_project(name="Lua", package_id="com.example.lua", template="lua-package")
    service.create_file(
        project.key,
        "scripts/lib/math.lua",
        """
local M = {}

function M.add(a, b)
    return a + b
end

function M:reset()
    self.value = 0
end

M.format = function(value)
    return tostring(value)
end

return M
""",
    )

    module = next(item for item in service.get_module_index(project.key) if item["key"] == "lib/math")

    assert module["exports"] == [
        {"name": "add", "params": ["a", "b"], "hasReturn": True, "returnKind": "value", "callStyle": "function"},
        {"name": "reset", "params": [], "hasReturn": False, "returnKind": "none", "callStyle": "method"},
        {"name": "format", "params": ["value"], "hasReturn": True, "returnKind": "value", "callStyle": "function"},
    ]


def test_init_lua_uses_parent_module_key_and_reports_collisions(tmp_path: Path) -> None:
    assert script_path_to_module_key("scripts/lib/init.lua") == "lib"
    service = ProjectService([tmp_path / "projects"], tmp_path / "builds")
    project = service.create_project(name="Blockly", package_id="com.example.blockly", template="blockly-package")
    service.create_file(project.key, "blockly/lib.xml", "<xml />")
    service.create_file(project.key, "scripts/lib/init.lua", "return {}\n")

    diagnostics = service.validate(project.key)

    assert any(item.code == "module.key_collision" and "模块 lib" in item.message for item in diagnostics)


def test_blockly_validator_reports_stale_project_module_function(tmp_path: Path) -> None:
    service = ProjectService([tmp_path / "projects"], tmp_path / "builds")
    project = service.create_project(name="Blockly", package_id="com.example.blockly", template="blockly-package")
    source = '''<xml xmlns="https://developers.google.com/blockly/xml">
      <block type="lua_project_module_call_expr">
        <field name="MODULE_VALUE">lib/math</field>
        <field name="FUNCTION_VALUE">add</field>
      </block>
    </xml>'''
    service.write_file(project.key, "blockly/main.xml", source)

    diagnostics = service.validate(project.key)

    assert any(item.code == "blockly.module_reference" and "lib/math" in item.message for item in diagnostics)


def test_moving_project_module_updates_saved_blockly_references(tmp_path: Path) -> None:
    service = ProjectService([tmp_path / "projects"], tmp_path / "builds")
    project = service.create_project(name="Blockly", package_id="com.example.blockly", template="blockly-package")
    service.create_file(project.key, "scripts/lib/math.lua", "local function add() end\nreturn { add = add }\n")
    source = '''<xml xmlns="https://developers.google.com/blockly/xml">
      <block type="lua_project_module_call_stmt">
        <field name="MODULE_VALUE">lib/math</field><field name="FUNCTION_VALUE">add</field>
      </block>
      <block type="lua_dofile_stmt"><field name="FILE_VALUE">scripts/lib/math.lua</field></block>
    </xml>'''
    service.write_file(project.key, "blockly/main.xml", source)
    service.create_directory(project.key, "scripts/shared")

    service.move_path(project.key, "scripts/lib/math.lua", "scripts/shared/math.lua")

    updated = service.read_file(project.key, "blockly/main.xml").content
    assert "shared/math" in updated
    assert "scripts/shared/math.lua" in updated
    assert "lib/math" not in updated
