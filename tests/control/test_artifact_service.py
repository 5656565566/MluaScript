from __future__ import annotations

import hashlib
import json
import os
import time
import zipfile
from pathlib import Path

import pytest
import yaml

import mluascript.control.workspace.artifact_service as artifact_module
from mluascript.control.workspace.artifact_service import (
    ArtifactService,
    ArtifactServiceError,
    cleanup_artifact_runtime_dir,
)
from mluascript.control.workspace.project_service import ProjectService
from mluascript.control.integration.script_run import RuntimeHostPlaceholder
from mluascript.runtime.engine import LuaEngine


def _manifest(project_type: str, *, package_id: str = "com.example.demo") -> dict[str, object]:
    entry: dict[str, object] = {"name": "主入口"}
    if project_type == "maa":
        entry["maa"] = "tasks/main.json"
    else:
        entry["script"] = "scripts/main.lua"
        if project_type == "blockly-package":
            entry["blockly"] = "blockly/main.xml"
    return {
        "schema": "mluascript.package/v1",
        "type": project_type,
        "package": {
            "id": package_id,
            "name": "演示包",
            "version": "1.0.0",
            "author": "Tester",
            "description": "可运行构建包",
        },
        "entrypoints": {"main": entry},
    }


def _write_package(
    path: Path,
    project_type: str,
    *,
    package_id: str = "com.example.demo",
    bad_checksum: bool = False,
    bad_readme_checksum: bool = False,
) -> Path:
    manifest = _manifest(project_type, package_id=package_id)
    files = {
        "mluascript.yaml": yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True).encode("utf-8"),
        "README.md": "# 演示包\n\n这是包说明。\n".encode("utf-8"),
    }
    if project_type == "maa":
        files["tasks/main.json"] = json.dumps({"entry": "main", "override": {"Main": {"enabled": True}}}).encode("utf-8")
        files["resources/maa/pipeline.json"] = b"{}"
    else:
        files["scripts/main.lua"] = b'return require("lib/helper").value\n'
        files["scripts/lib/helper.lua"] = b"return { value = 42 }\n"
        if project_type == "blockly-package":
            files["blockly/main.xml"] = b"<xml />\n"
    checksums = []
    for relative, content in sorted(files.items()):
        digest = (
            "0" * 64
            if (bad_checksum and relative == "mluascript.yaml") or (bad_readme_checksum and relative == "README.md")
            else hashlib.sha256(content).hexdigest()
        )
        checksums.append(f"{digest}  {relative}\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("META-INF/files.sha256", "".join(checksums))
        for relative, content in files.items():
            archive.writestr(relative, content)
    return path


@pytest.mark.parametrize("project_type", ["lua-package", "blockly-package"])
def test_prepare_script_package_verifies_and_extracts_locked_scripts(tmp_path: Path, project_type: str) -> None:
    builds = tmp_path / ".mluascript_web" / "builds"
    package = _write_package(builds / f"demo-{project_type}.mlspkg", project_type)
    service = ArtifactService(builds)

    artifact = next(item for item in service.list_artifacts() if item.kind == "package")
    prepared = service.prepare_run(artifact.id)

    assert artifact.kind == "package"
    assert artifact.entrypoint == "main"
    assert prepared.mode == "script"
    assert prepared.code.startswith('return require("lib/helper")')
    assert Path(prepared.script_path).relative_to(Path(prepared.cleanup_dir or "")) == Path("scripts/main.lua")
    assert (Path(prepared.cleanup_dir or "") / "mluascript.yaml").is_file()
    assert package.is_file()
    runtime = LuaEngine(
        path=Path(prepared.script_path).parent,
        host_api=RuntimeHostPlaceholder(),
        lock_project_modules=True,
    )
    assert runtime.execute(prepared.code) == 42

    prepared.cleanup()
    assert not Path(prepared.cleanup_dir or "").exists()


def test_prepare_maa_package_reads_descriptor_and_resources(tmp_path: Path) -> None:
    builds = tmp_path / ".mluascript_web" / "builds"
    _write_package(builds / "maa.mlspkg", "maa")
    service = ArtifactService(builds)

    artifact = next(item for item in service.list_artifacts() if item.kind == "maa")
    prepared = service.prepare_run(artifact.id)

    assert artifact.kind == "maa"
    assert prepared.mode == "pipeline"
    assert prepared.entry == "main"
    assert prepared.override == {"Main": {"enabled": True}}
    assert (Path(prepared.project_path) / "resources/maa/pipeline.json").is_file()
    prepared.cleanup()


def test_read_package_readme_verifies_checksum(tmp_path: Path) -> None:
    builds = tmp_path / ".mluascript_web" / "builds"
    _write_package(builds / "demo.mlspkg", "lua-package")
    service = ArtifactService(builds)
    artifact = next(item for item in service.list_artifacts() if item.kind == "package")

    readme = service.read_readme(artifact.id)

    assert artifact.has_readme is True
    assert readme.name == "演示包"
    assert readme.markdown == "# 演示包\n\n这是包说明。\n"


def test_read_package_readme_rejects_digest_mismatch(tmp_path: Path) -> None:
    builds = tmp_path / ".mluascript_web" / "builds"
    _write_package(builds / "broken-readme.mlspkg", "lua-package", bad_readme_checksum=True)
    service = ArtifactService(builds)
    artifact = next(item for item in service.list_artifacts() if item.kind == "package")

    with pytest.raises(ArtifactServiceError, match="README.md"):
        service.read_readme(artifact.id)


def test_package_checksum_failure_removes_runtime_directory(tmp_path: Path) -> None:
    builds = tmp_path / ".mluascript_web" / "builds"
    _write_package(builds / "broken.mlspkg", "lua-package", bad_checksum=True)
    service = ArtifactService(builds)
    artifact = next(item for item in service.list_artifacts() if item.kind == "package")

    with pytest.raises(ArtifactServiceError, match="摘要校验失败"):
        service.prepare_run(artifact.id)

    runtime_root = tmp_path / ".mluascript_web" / "runtime" / "tasks"
    assert list(runtime_root.iterdir()) == []


def test_catalog_keeps_latest_same_version_and_latest_single_file_build(tmp_path: Path) -> None:
    builds = tmp_path / ".mluascript_web" / "builds"
    old_package = _write_package(builds / "old.mlspkg", "lua-package")
    new_package = _write_package(builds / "new.mlspkg", "lua-package")
    old_lua = builds / "single" / "1111111111111111" / "single.lua"
    new_lua = builds / "single" / "2222222222222222" / "single.lua"
    old_lua.parent.mkdir(parents=True)
    new_lua.parent.mkdir(parents=True)
    old_lua.write_text("return 1", encoding="utf-8")
    new_lua.write_text("return 2", encoding="utf-8")
    now = time.time()
    os.utime(old_package, (now - 10, now - 10))
    os.utime(new_package, (now, now))
    os.utime(old_lua, (now - 10, now - 10))
    os.utime(new_lua, (now, now))

    artifacts = ArtifactService(builds).list_artifacts()

    package_items = [item for item in artifacts if item.kind == "package"]
    lua_items = [item for item in artifacts if item.kind == "lua"]
    assert len(package_items) == 1
    assert package_items[0].path.endswith("new.mlspkg")
    assert len(lua_items) == 1
    assert lua_items[0].path.endswith("2222222222222222/single.lua")


def test_catalog_restores_blockly_single_file_project_type(tmp_path: Path) -> None:
    projects = tmp_path / ".mluascript_web" / "projects"
    builds = tmp_path / ".mluascript_web" / "builds"
    project_service = ProjectService([projects], builds)
    project = project_service.create_project(name="flow", package_id="", template="blockly-file")
    result = project_service.build(
        project.key,
        generated_lua="return true\n",
        generated_from="flow.xml",
    )

    artifacts = ArtifactService(builds, project_service=project_service).list_artifacts()

    artifact = next(item for item in artifacts if item.path == Path(result.artifact_path).relative_to(tmp_path).as_posix())
    assert artifact.kind == "lua"
    assert artifact.project_type == "blockly-file"


def test_artifact_id_becomes_stale_when_file_changes(tmp_path: Path) -> None:
    builds = tmp_path / ".mluascript_web" / "builds"
    script = builds / "demo" / "1111111111111111" / "demo.lua"
    script.parent.mkdir(parents=True)
    script.write_text("return 1", encoding="utf-8")
    service = ArtifactService(builds)
    stale_id = next(item for item in service.list_artifacts() if item.source == "build").id

    script.write_text("return 22", encoding="utf-8")

    with pytest.raises(ArtifactServiceError, match="已被更新"):
        service.get_artifact(stale_id)


def test_runtime_cleanup_rejects_unowned_directory(tmp_path: Path) -> None:
    unowned = tmp_path / "keep"
    unowned.mkdir()

    assert cleanup_artifact_runtime_dir(unowned) is False
    assert unowned.is_dir()


def test_unchanged_package_manifest_is_reused_from_cache(monkeypatch, tmp_path: Path) -> None:
    builds = tmp_path / ".mluascript_web" / "builds"
    _write_package(builds / "cached.mlspkg", "lua-package")
    service = ArtifactService(builds)
    assert len(service.list_artifacts()) == 1

    monkeypatch.setattr(
        artifact_module.zipfile,
        "ZipFile",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("package reopened")),
    )

    assert len(service.list_artifacts()) == 1
