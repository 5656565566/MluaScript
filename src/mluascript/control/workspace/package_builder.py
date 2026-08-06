"""`mluascript.package/v1` 项目包校验和确定性打包。"""

from __future__ import annotations

import hashlib
import re
import uuid
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterable, Mapping

import yaml

from .project_models import ProjectDiagnostic, ProjectManifest


class ProjectManifestError(ValueError):
    """manifest 无法解析或不符合 v1 规范。"""

    def __init__(self, message: str, *, path: str | None = None, code: str = "manifest.invalid") -> None:
        super().__init__(message)
        self.code = code
        self.path = path


class ProjectPackageError(ValueError):
    """项目无法构建为有效 `.mlspkg`。"""

    def __init__(self, diagnostics: list[ProjectDiagnostic]) -> None:
        self.diagnostics = diagnostics
        message = "；".join(item.message for item in diagnostics) or "项目打包失败"
        super().__init__(message)


def normalize_package_path(raw_path: str) -> str:
    """校验并规范化包内相对路径，拒绝绝对路径和路径穿越。"""

    text = str(raw_path or "").strip().replace("\\", "/")
    if not text or "\x00" in text:
        raise ValueError("包内路径不能为空")
    windows_path = PureWindowsPath(text)
    if text.startswith("/") or windows_path.drive or windows_path.root:
        raise ValueError(f"包内路径必须是相对路径: {raw_path}")

    parts = [part for part in PurePosixPath(text).parts if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        raise ValueError(f"包内路径不允许路径穿越: {raw_path}")
    return "/".join(parts)


def _path_is_safe(project_root: Path, relative_path: str, *, allow_missing: bool = False) -> Path:
    normalized = normalize_package_path(relative_path)
    target = (project_root / Path(*PurePosixPath(normalized).parts)).resolve()
    try:
        target.relative_to(project_root.resolve())
    except ValueError as exc:
        raise ValueError(f"路径超出项目目录: {relative_path}") from exc

    current = project_root.resolve()
    for part in PurePosixPath(normalized).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"项目路径不允许符号链接: {relative_path}")
        if not current.exists() and allow_missing:
            break
    if not allow_missing and not target.exists():
        raise FileNotFoundError(relative_path)
    return target


def load_project_manifest(project_root: Path) -> ProjectManifest:
    """读取标准 manifest，并将 YAML/Pydantic 错误转换为领域异常。"""

    manifest_path = project_root / "mluascript.yaml"
    if not manifest_path.is_file():
        raise ProjectManifestError("缺少 mluascript.yaml", code="manifest.missing")
    try:
        raw_data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ProjectManifestError(f"读取 manifest 失败: {exc}") from exc
    if not isinstance(raw_data, dict):
        raise ProjectManifestError("manifest 顶层必须是对象")
    try:
        manifest = ProjectManifest.model_validate(raw_data)
    except Exception as exc:
        raise ProjectManifestError(f"manifest 结构校验失败: {exc}") from exc
    if manifest.schema_ != "mluascript.package/v1":
        raise ProjectManifestError(
            f"不支持的 manifest schema: {manifest.schema_}",
            code="manifest.schema",
        )
    return manifest


def _iter_project_files(project_root: Path) -> Iterable[tuple[str, Path]]:
    excluded_dirs = {".git", ".mluascript", "__pycache__", ".venv"}
    for path in sorted(project_root.rglob("*"), key=lambda item: item.as_posix().lower()):
        relative = path.relative_to(project_root)
        if any(part in excluded_dirs for part in relative.parts):
            continue
        if path.is_symlink():
            raise ValueError(f"项目包不允许符号链接: {relative.as_posix()}")
        if not path.is_file():
            continue
        yield normalize_package_path(relative.as_posix()), path


def _check_reference(
    project_root: Path,
    raw_path: str | None,
    diagnostics: list[ProjectDiagnostic],
    *,
    path_label: str,
    expect_directory: bool | None = None,
) -> None:
    if not raw_path:
        return
    try:
        normalized = normalize_package_path(raw_path)
        target = _path_is_safe(project_root, normalized)
    except (ValueError, FileNotFoundError) as exc:
        diagnostics.append(
            ProjectDiagnostic(
                code="path.invalid",
                message=f"{path_label}: {exc}",
                path=str(raw_path),
            )
        )
        return
    if expect_directory is True and not target.is_dir():
        diagnostics.append(ProjectDiagnostic(code="path.directory_required", message=f"{path_label} 必须是目录", path=normalized))
    if expect_directory is False and not target.is_file():
        diagnostics.append(ProjectDiagnostic(code="path.file_required", message=f"{path_label} 必须是文件", path=normalized))


def validate_project(project_root: Path) -> tuple[ProjectManifest | None, list[ProjectDiagnostic], list[tuple[str, Path]]]:
    """返回 manifest、结构化诊断和可打包文件列表。"""

    diagnostics: list[ProjectDiagnostic] = []
    try:
        manifest = load_project_manifest(project_root)
    except ProjectManifestError as exc:
        diagnostics.append(ProjectDiagnostic(code=exc.code, message=str(exc), path=exc.path))
        return None, diagnostics, []

    if not manifest.entrypoints:
        diagnostics.append(ProjectDiagnostic(code="entrypoint.missing", message="至少需要一个 entrypoint", path="entrypoints"))

    supported_types = {"lua-package", "blockly-package", "maa"}
    if manifest.project_type not in supported_types:
        diagnostics.append(
            ProjectDiagnostic(
                code="project.type",
                message=f"不可打包的项目类型: {manifest.project_type}",
                path="type",
            )
        )

    for entry_name, entry in manifest.entrypoints.items():
        required_field = {
            "lua-package": ("script", entry.script),
            "blockly-package": ("blockly", entry.blockly),
            "maa": ("maa", entry.maa),
        }.get(manifest.project_type)
        if required_field and not required_field[1]:
            diagnostics.append(
                ProjectDiagnostic(
                    code="entrypoint.type",
                    message=f"entrypoint {entry_name} 缺少 {required_field[0]} 入口",
                    path=f"entrypoints.{entry_name}.{required_field[0]}",
                )
            )
        _check_reference(project_root, entry.script, diagnostics, path_label=f"entrypoint {entry_name} script", expect_directory=False)
        if entry.blockly:
            _check_reference(project_root, entry.blockly, diagnostics, path_label=f"entrypoint {entry_name} blockly", expect_directory=False)
        if entry.maa:
            _check_reference(project_root, entry.maa, diagnostics, path_label=f"entrypoint {entry_name} maa", expect_directory=False)
        if entry.template:
            _check_reference(project_root, entry.template, diagnostics, path_label=f"entrypoint {entry_name} template", expect_directory=False)
        for model_id in entry.models.values():
            if model_id not in manifest.models:
                diagnostics.append(
                    ProjectDiagnostic(
                        code="model.undeclared",
                        message=f"entrypoint {entry_name} 引用了未声明模型: {model_id}",
                        path=f"entrypoints.{entry_name}.models",
                    )
                )

    for resource_name, resource_path in manifest.resources.items():
        _check_reference(project_root, resource_path, diagnostics, path_label=f"resource {resource_name}", expect_directory=True)

    for model_id, model in manifest.models.items():
        _check_reference(project_root, model.path, diagnostics, path_label=f"model {model_id}")

    try:
        files = list(_iter_project_files(project_root))
    except (OSError, ValueError) as exc:
        diagnostics.append(ProjectDiagnostic(code="file.invalid", message=str(exc)))
        files = []

    # 同一项目中大小写不同的文件在 Windows/zip 下无法稳定区分。
    seen_casefold: dict[str, str] = {}
    for relative, _ in files:
        key = relative.casefold()
        previous = seen_casefold.get(key)
        if previous and previous != relative:
            diagnostics.append(ProjectDiagnostic(code="file.collision", message=f"文件名大小写冲突: {previous} / {relative}", path=relative))
        seen_casefold[key] = relative

    # Blockly 可打包项目采用一对一镜像：blockly/a.xml -> scripts/a.lua。
    # 这里同时检查精确路径和大小写折叠路径，保证 Windows 与归档运行结果一致。
    from .module_paths import blockly_source_to_module_key, blockly_source_to_script_path, script_path_to_module_key

    blockly_sources = [relative for relative, _ in files if relative.casefold().endswith(".xml") and relative.casefold().startswith("blockly/")]
    for relative, _ in files:
        if manifest.project_type == "maa" and relative.casefold().endswith(".lua"):
            diagnostics.append(
                ProjectDiagnostic(code="maa.lua_unsupported", message=f"Maa 自动化项目不支持 Lua 脚本: {relative}", path=relative)
            )
    blockly_root_exists = (project_root / "blockly").exists()
    if manifest.project_type != "blockly-package":
        if blockly_root_exists and not blockly_sources:
            diagnostics.append(
                ProjectDiagnostic(
                    code="blockly.unsupported",
                    message=f"{manifest.project_type} 项目不支持 blockly/ 源目录",
                    path="blockly",
                )
            )
        for source_path in blockly_sources:
            diagnostics.append(
                ProjectDiagnostic(
                    code="blockly.unsupported",
                    message=f"{manifest.project_type} 项目不支持 Blockly 源文件: {source_path}",
                    path=source_path,
                )
            )
    else:
        from .module_index import validate_blockly_module_references

        for relative, _ in files:
            if relative.casefold().endswith(".xml") and not relative.casefold().startswith("blockly/"):
                diagnostics.append(
                    ProjectDiagnostic(
                        code="blockly.source_root",
                        message=f"Blockly 源文件必须位于 blockly/ 目录: {relative}",
                        path=relative,
                    )
                )
        generated_paths: dict[str, tuple[str, str]] = {}
        physical_files = {relative.casefold(): relative for relative, _ in files}
        module_origins: dict[str, tuple[str, str]] = {}
        for source_path in blockly_sources:
            generated_path = blockly_source_to_script_path(source_path)
            module_key = blockly_source_to_module_key(source_path)
            previous_module = module_origins.get(module_key.casefold())
            if previous_module and previous_module[1] != source_path:
                diagnostics.append(
                    ProjectDiagnostic(
                        code="module.key_collision",
                        message=f"多个 Blockly 源文件解析为同一模块 {module_key}: {previous_module[1]} / {source_path}",
                        path=source_path,
                    )
                )
            else:
                module_origins[module_key.casefold()] = (module_key, source_path)
            folded = generated_path.casefold()
            previous = generated_paths.get(folded)
            if previous and previous[0] != generated_path:
                diagnostics.append(
                    ProjectDiagnostic(
                        code="blockly.generated_collision",
                        message=f"Blockly 生成 Lua 路径大小写冲突: {previous[1]} / {source_path} -> {generated_path}",
                        path=source_path,
                    )
                )
            elif previous:
                diagnostics.append(
                    ProjectDiagnostic(
                        code="blockly.generated_collision",
                        message=f"多个 Blockly 文件生成同一个 Lua: {previous[1]} / {source_path} -> {generated_path}",
                        path=source_path,
                    )
                )
            generated_paths[folded] = (generated_path, source_path)

            physical_path = physical_files.get(folded)
            if physical_path is not None:
                diagnostics.append(
                    ProjectDiagnostic(
                        code="blockly.script_collision",
                        message=f"Blockly 生成 Lua 与项目文件冲突: {source_path} -> {physical_path}",
                        path=physical_path,
                    )
                )
        for relative, _ in files:
            if not relative.casefold().startswith("scripts/") or not relative.casefold().endswith(".lua"):
                continue
            module_key = script_path_to_module_key(relative)
            previous_module = module_origins.get(module_key.casefold())
            if previous_module and previous_module[1] != relative:
                diagnostics.append(
                    ProjectDiagnostic(
                        code="module.key_collision",
                        message=f"多个源文件解析为同一模块 {module_key}: {previous_module[1]} / {relative}",
                        path=relative,
                    )
                )
            else:
                module_origins[module_key.casefold()] = (module_key, relative)
        for source_path, message in validate_blockly_module_references(project_root):
            diagnostics.append(
                ProjectDiagnostic(code="blockly.module_reference", message=message, path=source_path)
            )

    return manifest, diagnostics, files


def _zip_entry(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(filename=name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 0
    info.external_attr = 0o644 << 16
    info.flag_bits |= 0x800
    return info


def _hash_file(path: Path) -> str:
    """按块计算文件摘要，避免模型或资源文件整体进入内存。"""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _write_file_entry(archive: zipfile.ZipFile, relative: str, source: Path) -> str:
    """把文件流式写入 ZIP，并返回实际写入内容的摘要。"""

    digest = hashlib.sha256()
    with source.open("rb") as input_stream, archive.open(_zip_entry(relative), "w", force_zip64=True) as output_stream:
        while chunk := input_stream.read(1024 * 1024):
            digest.update(chunk)
            output_stream.write(chunk)
    return digest.hexdigest()


def _write_bytes_entry(archive: zipfile.ZipFile, relative: str, content: bytes) -> str:
    archive.writestr(_zip_entry(relative), content)
    return _hash_bytes(content)


def build_project_package(
    project_root: Path,
    artifact_root: Path,
    project_key: str,
    *,
    generated_lua: str | None = None,
    generated_lua_by_source: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """校验项目并生成时间戳稳定的 `.mlspkg` 文件。"""

    project_root = project_root.resolve()
    artifact_root = artifact_root.resolve()
    manifest, diagnostics, files = validate_project(project_root)
    errors = [item for item in diagnostics if item.severity == "error"]
    if errors or manifest is None:
        raise ProjectPackageError(diagnostics)

    generated_entries: dict[str, bytes] = {}
    if manifest.project_type == "blockly-package":
        from .module_paths import blockly_source_to_script_path

        blockly_sources = [relative for relative, _ in files if relative.casefold().endswith(".xml") and relative.casefold().startswith("blockly/")]
        source_map: dict[str, str] = {}
        for raw_source, raw_lua in (generated_lua_by_source or {}).items():
            try:
                normalized_source = normalize_package_path(raw_source)
                blockly_source_to_script_path(normalized_source)
            except ValueError as exc:
                raise ProjectPackageError(
                    [ProjectDiagnostic(code="blockly.generated_source", message=str(exc), path=str(raw_source))]
                ) from exc
            source_map[normalized_source] = str(raw_lua or "")

        # 兼容旧客户端的单入口请求；多 XML 项目必须使用完整映射。
        if not source_map and len(blockly_sources) == 1 and str(generated_lua or "").strip():
            source_map[blockly_sources[0]] = str(generated_lua)

        missing_sources = [source for source in blockly_sources if not source_map.get(source, "").strip()]
        unknown_sources = sorted(set(source_map) - set(blockly_sources))
        if missing_sources or unknown_sources:
            details = []
            if missing_sources:
                details.append(f"缺少生成结果: {', '.join(missing_sources)}")
            if unknown_sources:
                details.append(f"不存在的 Blockly 源文件: {', '.join(unknown_sources)}")
            raise ProjectPackageError(
                [ProjectDiagnostic(code="blockly.generated_lua", message="；".join(details))]
            )
        for source_path, lua_code in source_map.items():
            generated_path = blockly_source_to_script_path(source_path)
            generated_entries[generated_path] = lua_code.encode("utf-8")

        manifest_data = manifest.model_dump(by_alias=True, exclude_none=True)
        for entrypoint in manifest_data.get("entrypoints", {}).values():
            source_path = entrypoint.get("blockly")
            if source_path:
                entrypoint["script"] = blockly_source_to_script_path(source_path)
        generated_entries["mluascript.yaml"] = yaml.safe_dump(
            manifest_data,
            sort_keys=False,
            allow_unicode=True,
        ).encode("utf-8")

    artifact_root.mkdir(parents=True, exist_ok=True)
    package_id = re.sub(r"[^A-Za-z0-9._-]+", "_", manifest.package.id)
    version = re.sub(r"[^A-Za-z0-9._-]+", "_", manifest.package.version)
    build_id = uuid.uuid4().hex[:16]
    filename = f"{package_id}-{version}-{build_id}.mlspkg"
    output_path = artifact_root / filename
    temp_path = artifact_root / f".{filename}.tmp"

    prepared_files: list[tuple[str, Path | None, bytes | None, str]] = []
    for relative, source in files:
        if relative in generated_entries:
            continue
        prepared_files.append((relative, source, None, _hash_file(source)))
    for relative, content in generated_entries.items():
        prepared_files.append((relative, None, content, _hash_bytes(content)))
    prepared_files.sort(key=lambda item: item[0])
    file_hashes = [(relative, digest) for relative, _, _, digest in prepared_files]
    try:
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            checksum_content = "".join(f"{digest}  {relative}\n" for relative, digest in file_hashes)
            archive.writestr(_zip_entry("META-INF/files.sha256"), checksum_content.encode("utf-8"))
            for relative, source, content, expected_digest in prepared_files:
                actual_digest = (
                    _write_file_entry(archive, relative, source)
                    if source is not None
                    else _write_bytes_entry(archive, relative, content or b"")
                )
                if actual_digest != expected_digest:
                    raise ProjectPackageError(
                        [ProjectDiagnostic(code="file.changed", message=f"打包期间文件发生变化: {relative}", path=relative)]
                    )
        temp_path.replace(output_path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise

    package_hash = _hash_file(output_path)
    return {
        "build_id": build_id,
        "project_key": project_key,
        "filename": filename,
        "artifact_path": str(output_path),
        "size": output_path.stat().st_size,
        "sha256": package_hash,
        "files": [relative for relative, _ in file_hashes],
        "model_count": len(manifest.models),
    }
