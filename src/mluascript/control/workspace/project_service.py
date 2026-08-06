"""项目目录的创建、发现、文件访问和打包入口。"""

from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import uuid
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Iterable, Iterator, Mapping, Sequence

import yaml

from .package_builder import (
    ProjectManifestError,
    build_project_package,
    load_project_manifest,
    normalize_package_path,
    validate_project,
)
from .module_paths import blockly_source_to_script_path
from .module_index import build_project_module_index
from .project_models import (
    ProjectBuildResult,
    ProjectDebugTarget,
    ProjectDiagnostic,
    ProjectFileContent,
    ProjectManifest,
    ProjectPipelineDebugTarget,
    ProjectSummary,
    ProjectTreeItem,
)


_TEXT_FILE_SUFFIXES = {
    ".css",
    ".csv",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".lua",
    ".md",
    ".toml",
    ".ts",
    ".txt",
    ".vue",
    ".xml",
    ".yaml",
    ".yml",
}

_PROJECT_TEMPLATE_ALIASES = {
    "blank-lua": "lua-package",
    "blank-blockly": "blockly-package",
}
_PACKAGE_PROJECT_TYPES = {"lua-package", "blockly-package", "maa"}
_SINGLE_PROJECT_TYPES = {"lua-file", "blockly-file"}
_PROJECT_TEMPLATES = _PACKAGE_PROJECT_TYPES | _SINGLE_PROJECT_TYPES


class ProjectServiceError(ValueError):
    """项目服务的可展示错误。"""


class ProjectNotFoundError(ProjectServiceError):
    """项目 key 不存在或不在受控项目根目录下。"""


class ProjectService:
    """管理允许 Web 前端访问的项目根目录。

    前端只持有不可推导真实路径的 project key。所有路径解析都重新落在
    配置的根目录内，避免把任意宿主机路径暴露为 API 参数。
    """

    def __init__(self, project_roots: Sequence[str | Path], artifact_root: str | Path | None = None) -> None:
        roots = [Path(item).expanduser() for item in project_roots if str(item).strip()]
        if not roots:
            roots = [Path.cwd() / "projects"]
        self.project_roots = [item.resolve() for item in roots]
        self.artifact_root = Path(artifact_root or (Path.cwd() / ".mluascript" / "builds")).resolve()
        self._build_artifacts: dict[tuple[str, str], Path] = {}

    def _project_key(self, project_root: Path) -> str:
        normalized = str(project_root.resolve()).casefold().encode("utf-8")
        return hashlib.sha256(normalized).hexdigest()[:24]

    def _relative_directory(self, project_root: Path) -> str:
        for root in self.project_roots:
            try:
                return project_root.relative_to(root).as_posix() or project_root.name
            except ValueError:
                continue
        return project_root.name

    def _iter_project_roots(self) -> Iterable[Path]:
        for configured_root in self.project_roots:
            if not configured_root.exists():
                continue
            if configured_root.is_symlink():
                continue
            manifest_roots: set[Path] = set()
            if (configured_root / "mluascript.yaml").is_file():
                manifest_roots.add(configured_root.resolve())
            for manifest_path in configured_root.rglob("mluascript.yaml"):
                if manifest_path.parent == configured_root or manifest_path.is_symlink():
                    continue
                project_root = manifest_path.parent.resolve()
                try:
                    project_root.relative_to(configured_root)
                except ValueError:
                    continue
                if project_root.is_dir():
                    manifest_roots.add(project_root)

            yield from sorted(manifest_roots, key=lambda item: item.as_posix().casefold())
            for candidate in configured_root.rglob("*"):
                if not candidate.is_dir() or candidate.is_symlink():
                    continue
                resolved = candidate.resolve()
                if any(resolved == root or root in resolved.parents for root in manifest_roots):
                    continue
                if self._single_project_source(resolved) is not None:
                    yield resolved

    def _single_project_source(self, project_root: Path) -> Path | None:
        """识别“同名目录/同名源文件”的单文件项目。"""

        if (project_root / "mluascript.yaml").exists():
            return None
        for suffix in (".xml", ".lua"):
            candidate = project_root / f"{project_root.name}{suffix}"
            if candidate.is_file() and not candidate.is_symlink():
                return candidate
        return None

    def _project_type(self, project_root: Path) -> str:
        source = self._single_project_source(project_root)
        if source is not None:
            return "blockly-file" if source.suffix.lower() == ".xml" else "lua-file"
        try:
            return load_project_manifest(project_root).project_type
        except ProjectManifestError:
            return "lua-package"

    def _primary_path(self, project_root: Path) -> str:
        source = self._single_project_source(project_root)
        if source is not None:
            return source.name
        try:
            manifest = load_project_manifest(project_root)
        except ProjectManifestError:
            return ""
        for entrypoint in manifest.entrypoints.values():
            for path in (entrypoint.blockly, entrypoint.script, entrypoint.maa):
                if path:
                    return path
        return ""

    def _resolve_project(self, project_key: str) -> Path:
        key = str(project_key or "").strip()
        for project_root in self._iter_project_roots():
            if self._project_key(project_root) == key:
                return project_root
        raise ProjectNotFoundError("项目不存在或已移除")

    def _summary(self, project_root: Path) -> ProjectSummary:
        project_key = self._project_key(project_root)
        project_type = self._project_type(project_root)
        if project_type in _SINGLE_PROJECT_TYPES:
            source = self._single_project_source(project_root)
            return ProjectSummary(
                key=project_key,
                name=project_root.name,
                package_id="",
                version="",
                directory=self._relative_directory(project_root),
                project_type=project_type,
                buildable=True,
                primary_path=source.name if source else "",
                valid=source is not None,
                entrypoints=["main"],
                file_count=1 if source else 0,
            )
        manifest, diagnostics, files = validate_project(project_root)
        if manifest is None:
            return ProjectSummary(
                key=project_key,
                name=project_root.name,
                package_id="",
                version="",
                directory=self._relative_directory(project_root),
                project_type=project_type,
                buildable=project_type in _PACKAGE_PROJECT_TYPES,
                valid=False,
                diagnostics=diagnostics,
            )
        return ProjectSummary(
            key=project_key,
            name=manifest.package.name,
            package_id=manifest.package.id,
            version=manifest.package.version,
            author=manifest.package.author,
            description=manifest.package.description,
            directory=self._relative_directory(project_root),
            project_type=manifest.project_type,
            buildable=manifest.project_type in _PACKAGE_PROJECT_TYPES,
            primary_path=self._primary_path(project_root),
            valid=not any(item.severity == "error" for item in diagnostics),
            entrypoints=list(manifest.entrypoints.keys()),
            model_count=len(manifest.models),
            file_count=len(files),
            diagnostics=diagnostics,
        )

    def list_projects(self) -> list[ProjectSummary]:
        """发现配置根目录下的项目。"""

        projects: dict[str, ProjectSummary] = {}
        for project_root in self._iter_project_roots():
            summary = self._summary(project_root)
            projects[summary.key] = summary
        return sorted(projects.values(), key=lambda item: (item.name.casefold(), item.directory.casefold()))

    def get_project(self, project_key: str) -> ProjectSummary:
        return self._summary(self._resolve_project(project_key))

    def open_project(self, project_key: str) -> dict[str, Any]:
        project_root = self._resolve_project(project_key)
        summary = self._summary(project_root)
        manifest_data: dict[str, Any] = {}
        try:
            manifest = load_project_manifest(project_root)
            manifest_data = manifest.model_dump(by_alias=True, exclude_none=True)
        except ProjectManifestError:
            pass
        return {
            "project": summary.model_dump(),
            "manifest": manifest_data,
            "tree": [item.model_dump() for item in self.list_tree(project_key)],
        }

    def create_project(
        self,
        *,
        name: str,
        package_id: str,
        version: str = "0.1.0",
        author: str = "",
        description: str = "",
        directory: str = "",
        template: str = "lua-package",
    ) -> ProjectSummary:
        """以临时目录写完模板后原子移动，避免出现半初始化项目。"""

        project_name = str(name or "").strip()
        package_identifier = str(package_id or "").strip()
        package_version = str(version or "").strip()
        template = _PROJECT_TEMPLATE_ALIASES.get(template, template)
        if template not in _PROJECT_TEMPLATES:
            raise ProjectServiceError(f"不支持的项目模板: {template}")
        if template == "blockly-file" and project_name.lower().endswith(".xml"):
            project_name = project_name[:-4].strip()
        if template == "lua-file" and project_name.lower().endswith(".lua"):
            project_name = project_name[:-4].strip()
        if not project_name:
            raise ProjectServiceError("项目名称不能为空")
        if template in _PACKAGE_PROJECT_TYPES and (not package_identifier or not package_version):
            raise ProjectServiceError("项目名称、包 ID 和版本不能为空")

        root = self.project_roots[0]
        root.mkdir(parents=True, exist_ok=True)
        folder = self._safe_project_directory(directory or self._slugify(project_name))
        target = (root / Path(*PurePosixPath(folder).parts)).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ProjectServiceError("项目目录必须位于配置的项目根目录内") from exc
        if target.exists():
            raise ProjectServiceError("项目目录已存在")

        temporary = root / f".{target.name}.tmp-{uuid.uuid4().hex[:12]}"
        try:
            if template in _SINGLE_PROJECT_TYPES:
                self._write_single_file_project(temporary, target.name, template)
            else:
                manifest = self._build_template_manifest(
                    project_name,
                    package_identifier,
                    package_version,
                    template,
                    author=str(author or "").strip(),
                    description=str(description or "").strip(),
                )
                self._write_template_project(temporary, manifest, template)
            if target.exists():
                raise ProjectServiceError("项目目录已存在")
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary.replace(target)
        except Exception:
            if temporary.exists():
                shutil.rmtree(temporary, ignore_errors=True)
            raise
        return self._summary(target)

    def _write_single_file_project(self, target: Path, project_directory: str, template: str) -> None:
        target.mkdir(parents=True, exist_ok=False)
        suffix = ".xml" if template == "blockly-file" else ".lua"
        content = (
            '<xml xmlns="https://developers.google.com/blockly/xml"></xml>\n'
            if template == "blockly-file"
            else "-- MluaScript Lua script\n\n"
        )
        (target / f"{project_directory}{suffix}").write_bytes(content.encode("utf-8"))

    def update_project(
        self,
        project_key: str,
        *,
        name: str,
        package_id: str,
        version: str,
        author: str = "",
        description: str = "",
    ) -> ProjectSummary:
        """原子更新 manifest 中的项目身份信息，不移动项目目录。"""

        project_name = str(name or "").strip()
        package_identifier = str(package_id or "").strip()
        package_version = str(version or "").strip()
        if not project_name or not package_identifier or not package_version:
            raise ProjectServiceError("项目名称、包 ID 和版本不能为空")

        project_root = self._resolve_project(project_key)
        if self._project_type(project_root) in _SINGLE_PROJECT_TYPES:
            raise ProjectServiceError("单文件项目名称由目录和源文件名称决定")
        try:
            manifest = load_project_manifest(project_root).model_dump(by_alias=True, exclude_none=True)
        except ProjectManifestError as exc:
            raise ProjectServiceError(f"项目清单无效: {exc}") from exc
        manifest["package"] = {
            **manifest.get("package", {}),
            "id": package_identifier,
            "name": project_name,
            "version": package_version,
            "author": str(author or "").strip(),
            "description": str(description or "").strip(),
        }
        normalized = ProjectManifest.model_validate(manifest).model_dump(by_alias=True, exclude_none=True)

        self._write_manifest(project_root, normalized)
        return self._summary(project_root)

    def _write_manifest(self, project_root: Path, manifest: ProjectManifest | dict[str, Any]) -> None:
        """校验并原子写入项目清单，避免各项目信息操作重复持久化细节。"""

        normalized = ProjectManifest.model_validate(manifest).model_dump(by_alias=True, exclude_none=True)
        target = project_root / "mluascript.yaml"
        temporary = target.parent / f".{target.name}.save-{uuid.uuid4().hex[:12]}"
        try:
            temporary.write_bytes(yaml.safe_dump(normalized, sort_keys=False, allow_unicode=True).encode("utf-8"))
            temporary.replace(target)
        except Exception:
            if temporary.exists():
                temporary.unlink()
            raise

    def _remap_manifest_file(self, manifest: ProjectManifest, source_path: str, destination_path: str) -> bool:
        """同步清单中对单个文件的引用；目录结构仍由清单约束保护。"""

        changed = False
        for entrypoint in manifest.entrypoints.values():
            for field_name in ("script", "blockly", "maa", "template"):
                if getattr(entrypoint, field_name) == source_path:
                    setattr(entrypoint, field_name, destination_path)
                    changed = True
            for model_name, model_path in entrypoint.models.items():
                if model_path == source_path:
                    entrypoint.models[model_name] = destination_path
                    changed = True
        for resource_name, resource_path in manifest.resources.items():
            if resource_path == source_path:
                manifest.resources[resource_name] = destination_path
                changed = True
        for model in manifest.models.values():
            if model.path == source_path:
                model.path = destination_path
                changed = True
        return changed

    def _safe_project_directory(self, raw_directory: str) -> str:
        text = str(raw_directory or "").strip().replace("\\", "/")
        if not text:
            raise ProjectServiceError("项目目录不能为空")
        try:
            normalized = normalize_package_path(text)
        except ValueError as exc:
            raise ProjectServiceError(str(exc)) from exc
        if any(part.startswith(".") for part in PurePosixPath(normalized).parts):
            raise ProjectServiceError("项目目录不允许隐藏路径")
        return normalized

    def _slugify(self, name: str) -> str:
        value = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", name)
        value = re.sub(r"\s+", "-", value).strip(".-_ ")
        return value or "project"

    def _build_template_manifest(
        self,
        name: str,
        package_id: str,
        version: str,
        template: str,
        *,
        author: str,
        description: str,
    ) -> dict[str, Any]:
        entrypoint: dict[str, str] = {"name": "主入口"}
        if template == "lua-package":
            entrypoint["script"] = "scripts/main.lua"
        if template == "blockly-package":
            entrypoint["blockly"] = "blockly/main.xml"
        if template == "maa":
            entrypoint["maa"] = "tasks/main.json"
        resources = {"assets": "resources/assets"}
        if template == "maa":
            resources["maa"] = "resources/maa"
        return {
            "schema": "mluascript.package/v1",
            "type": template,
            "package": {
                "id": package_id,
                "name": name,
                "version": version,
                "author": author,
                "description": description,
            },
            "runtime": {"lua": "5.4", "mluascript": ">=1.0.0"},
            "entrypoints": {"main": entrypoint},
            "resources": resources,
            "models": {},
            "capabilities": {"device": template == "maa", "network": False, "llm": False, "package_files": "read"},
        }

    def _write_template_project(self, target: Path, manifest: dict[str, Any], template: str) -> None:
        directories = ["resources/assets", "models/ocr", "models/nnd"]
        if template == "lua-package":
            directories.extend(["scripts/tasks", "scripts/lib"])
        if template == "blockly-package":
            # Blockly 源目录和生成后的虚拟 scripts 目录保持相同的模块层级。
            directories.extend(["blockly/lib", "scripts/lib"])
        if template == "maa":
            directories.extend(["tasks", "resources/maa", "templates"])
        for directory in directories:
            (target / Path(*PurePosixPath(directory).parts)).mkdir(parents=True, exist_ok=True)
        (target / "mluascript.yaml").write_bytes(
            yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True).encode("utf-8")
        )
        if template == "lua-package":
            lua_source = "-- MluaScript Lua package entrypoint\n\nprint('Hello from MluaScript')\n"
            (target / "scripts" / "main.lua").write_bytes(lua_source.encode("utf-8"))
        if template == "blockly-package":
            (target / "blockly" / "main.xml").write_bytes(
                '<xml xmlns="https://developers.google.com/blockly/xml"></xml>\n'.encode("utf-8")
            )
        if template == "maa":
            # Maa 项目用源码描述文件声明调试入口；默认 main 便于新项目直接修改和运行。
            (target / "tasks" / "main.json").write_bytes(
                json.dumps({"entry": "main", "override": {}}, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
            )
        (target / "README.md").write_bytes(f"# {manifest['package']['name']}\n\nMluaScript v1 项目。\n".encode("utf-8"))

    def _manifest_owned_paths(self, project_root: Path) -> set[str]:
        """返回不能由通用文件树改名的 manifest 和声明路径。"""

        try:
            manifest = load_project_manifest(project_root)
        except ProjectManifestError as exc:
            raise ProjectServiceError(f"项目清单无效: {exc}") from exc

        referenced = {"mluascript.yaml"}
        for entrypoint in manifest.entrypoints.values():
            referenced.update(path for path in (entrypoint.script, entrypoint.blockly, entrypoint.maa, entrypoint.template) if path)
            referenced.update(path for path in entrypoint.models.values() if path)
        referenced.update(path for path in manifest.resources.values() if path)
        referenced.update(model.path for model in manifest.models.values() if model.path)

        protected: set[str] = set()
        for raw_path in referenced:
            parts = PurePosixPath(str(raw_path).replace("\\", "/")).parts
            for index in range(1, len(parts) + 1):
                protected.add(PurePosixPath(*parts[:index]).as_posix())
        return protected

    def _resolve_project_path(self, project_key: str, relative_path: str, *, allow_missing: bool = False) -> tuple[Path, str]:
        project_root = self._resolve_project(project_key)
        try:
            normalized = normalize_package_path(relative_path)
        except ValueError as exc:
            raise ProjectServiceError(str(exc)) from exc
        target = (project_root / Path(*PurePosixPath(normalized).parts)).resolve()
        try:
            target.relative_to(project_root.resolve())
        except ValueError as exc:
            raise ProjectServiceError("路径超出项目目录") from exc
        current = project_root.resolve()
        for part in PurePosixPath(normalized).parts:
            current = current / part
            if current.is_symlink():
                raise ProjectServiceError("项目路径不允许符号链接")
            if not current.exists() and allow_missing:
                break
        if not allow_missing and not target.exists():
            raise ProjectServiceError("文件不存在")
        return target, normalized

    def list_tree(self, project_key: str) -> list[ProjectTreeItem]:
        project_root = self._resolve_project(project_key)
        items: list[ProjectTreeItem] = []
        excluded_dirs = {".git", ".mluascript", "__pycache__", ".venv"}
        for item in sorted(project_root.rglob("*"), key=lambda path: path.as_posix().casefold()):
            relative = item.relative_to(project_root)
            if any(part in excluded_dirs for part in relative.parts) or item.is_symlink():
                continue
            kind = "directory" if item.is_dir() else "file"
            stat = item.stat()
            items.append(
                ProjectTreeItem(
                    path=relative.as_posix(),
                    name=item.name,
                    kind=kind,
                    size=stat.st_size if kind == "file" else 0,
                    mtime=stat.st_mtime,
                )
            )
        return items

    def get_tree_item(self, project_key: str, relative_path: str) -> ProjectTreeItem:
        target, normalized = self._resolve_project_path(project_key, relative_path)
        kind = "directory" if target.is_dir() else "file"
        stat = target.stat()
        return ProjectTreeItem(
            path=normalized,
            name=target.name,
            kind=kind,
            size=stat.st_size if kind == "file" else 0,
            mtime=stat.st_mtime,
        )

    def create_directory(self, project_key: str, relative_path: str) -> ProjectTreeItem:
        """在项目内创建单个目录，父目录必须已经存在。"""

        project_root = self._require_package_project(project_key)
        target, normalized = self._resolve_project_path(project_key, relative_path, allow_missing=True)
        self._validate_package_path_policy(project_root, normalized, is_directory=True)
        if target.exists():
            raise ProjectServiceError("目录或文件已存在")
        if not target.parent.is_dir():
            raise ProjectServiceError("父目录不存在")
        target.mkdir()
        return self.get_tree_item(project_key, normalized)

    def create_file(self, project_key: str, relative_path: str, content: str = "") -> ProjectFileContent:
        """创建新的 UTF-8 文本文件，不覆盖项目中的现有内容。"""

        project_root = self._require_package_project(project_key)
        target, normalized = self._resolve_project_path(project_key, relative_path, allow_missing=True)
        self._validate_package_path_policy(project_root, normalized)
        if target.exists():
            raise ProjectServiceError("目录或文件已存在")
        if not target.parent.is_dir():
            raise ProjectServiceError("父目录不存在")
        try:
            with target.open("x", encoding="utf-8", newline="") as stream:
                stream.write(content)
        except FileExistsError as exc:
            raise ProjectServiceError("目录或文件已存在") from exc
        return self.read_file(project_key, normalized)

    def delete_file(self, project_key: str, relative_path: str) -> str:
        """删除项目内的自定义文件；入口和 manifest 管理文件必须先调整项目结构。"""

        project_root = self._require_package_project(project_key)
        target, normalized = self._resolve_project_path(project_key, relative_path)
        if not target.is_file():
            raise ProjectServiceError("只能删除文件，目录删除暂不支持")
        if normalized in self._manifest_owned_paths(project_root):
            raise ProjectServiceError("manifest 管理的项目文件不能直接删除")
        try:
            target.unlink()
        except OSError as exc:
            raise ProjectServiceError(f"删除文件失败: {exc}") from exc
        return normalized

    def rename_path(self, project_key: str, relative_path: str, new_name: str) -> ProjectTreeItem:
        """重命名项目文件或自定义目录，并同步受 manifest 管理的文件引用。"""

        name = str(new_name or "").strip()
        invalid_character = any(character in '<>:"/\\|?*' or ord(character) < 32 for character in name)
        if (
            not name
            or name in {".", ".."}
            or name.startswith(".")
            or name.endswith((".", " "))
            or invalid_character
        ):
            raise ProjectServiceError("新名称必须是不含路径分隔符的普通文件名")

        self._require_package_project(project_key)
        source, normalized = self._resolve_project_path(project_key, relative_path)
        destination = (PurePosixPath(normalized).parent / name).as_posix()
        project_root = self._resolve_project(project_key)
        protected_paths = self._manifest_owned_paths(project_root)
        if normalized == "mluascript.yaml" or (source.is_dir() and normalized in protected_paths):
            raise ProjectServiceError("manifest 管理的项目结构不能在文件树中重命名或移动")
        if source.is_file() and normalized in protected_paths:
            target, destination_normalized = self._resolve_project_path(project_key, destination, allow_missing=True)
            self._validate_package_path_policy(project_root, destination_normalized)
            if target.exists():
                raise ProjectServiceError("目录或文件已存在")
            manifest = load_project_manifest(project_root)
            manifest_path = project_root / "mluascript.yaml"
            original_manifest = manifest_path.read_bytes()
            if not self._remap_manifest_file(manifest, normalized, destination_normalized):
                raise ProjectServiceError("manifest 管理的项目文件引用无法更新")
            try:
                source.replace(target)
                self._write_manifest(project_root, manifest)
                self._remap_blockly_module_references(
                    project_root,
                    normalized,
                    destination_normalized,
                    is_directory=False,
                )
            except Exception as exc:
                if target.exists() and not source.exists():
                    target.replace(source)
                manifest_path.write_bytes(original_manifest)
                if isinstance(exc, ProjectServiceError):
                    raise
                raise ProjectServiceError(f"重命名失败: {exc}") from exc
            return self.get_tree_item(project_key, destination_normalized)
        return self.move_path(project_key, normalized, destination)

    def move_path(self, project_key: str, source_path: str, destination_path: str) -> ProjectTreeItem:
        """在项目内移动自定义文件或目录，不覆盖目标内容。"""

        self._require_package_project(project_key)
        source, normalized = self._resolve_project_path(project_key, source_path)
        destination, destination_normalized = self._resolve_project_path(
            project_key,
            destination_path,
            allow_missing=True,
        )
        if normalized == destination_normalized:
            return self.get_tree_item(project_key, normalized)

        project_root = self._resolve_project(project_key)
        if normalized in self._manifest_owned_paths(project_root):
            raise ProjectServiceError("manifest 管理的项目结构不能在文件树中重命名或移动")
        if destination.exists():
            raise ProjectServiceError("目录或文件已存在")
        if not destination.parent.is_dir():
            raise ProjectServiceError("目标父目录不存在")
        self._validate_moved_tree_policy(project_root, source, destination_normalized)
        if source.is_dir():
            try:
                destination.relative_to(source)
            except ValueError:
                pass
            else:
                raise ProjectServiceError("目录不能移动到自身或其子目录")
        source_is_directory = source.is_dir()
        try:
            source.replace(destination)
            self._remap_blockly_module_references(
                project_root,
                normalized,
                destination_normalized,
                is_directory=source_is_directory,
            )
        except (OSError, ProjectServiceError) as exc:
            if destination.exists() and not source.exists():
                destination.replace(source)
            if isinstance(exc, ProjectServiceError):
                raise
            raise ProjectServiceError(f"移动失败: {exc}") from exc
        return self.get_tree_item(project_key, destination_normalized)

    @contextmanager
    def open_binary_writer(
        self,
        project_key: str,
        relative_path: str,
        *,
        overwrite: bool = False,
    ) -> Iterator[tuple[BinaryIO, str]]:
        """以临时文件接收二进制内容，完整写入后再原子替换目标。"""

        project_root = self._require_package_project(project_key)
        target, normalized = self._resolve_project_path(project_key, relative_path, allow_missing=True)
        self._validate_package_path_policy(project_root, normalized)
        if target.exists() and (not overwrite or not target.is_file()):
            raise ProjectServiceError("目录或文件已存在")
        if not target.parent.is_dir():
            raise ProjectServiceError("父目录不存在")

        temporary = target.parent / f".{target.name}.upload-{uuid.uuid4().hex[:12]}"
        try:
            with temporary.open("xb") as stream:
                yield stream, normalized
            temporary.replace(target)
        except Exception:
            if temporary.exists():
                temporary.unlink()
            raise

    def get_file_path(self, project_key: str, relative_path: str) -> tuple[Path, str]:
        """返回受控项目中的文件路径，供流式下载使用。"""

        target, normalized = self._resolve_project_path(project_key, relative_path)
        if not target.is_file():
            raise ProjectServiceError("目标不是文件")
        return target, normalized

    def read_file(self, project_key: str, relative_path: str) -> ProjectFileContent:
        target, normalized = self._resolve_project_path(project_key, relative_path)
        if not target.is_file():
            raise ProjectServiceError("目标不是文件")
        if target.suffix.lower() not in _TEXT_FILE_SUFFIXES:
            stat = target.stat()
            return ProjectFileContent(
                path=normalized,
                name=target.name,
                size=stat.st_size,
                mtime=stat.st_mtime,
                encoding=None,
            )
        raw = target.read_bytes()
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            return ProjectFileContent(
                path=normalized,
                name=target.name,
                size=len(raw),
                mtime=target.stat().st_mtime,
                encoding=None,
            )
        return ProjectFileContent(
            path=normalized,
            name=target.name,
            size=len(raw),
            mtime=target.stat().st_mtime,
            content=content,
        )

    def write_file(self, project_key: str, relative_path: str, content: str, expected_mtime: float | None = None) -> ProjectFileContent:
        project_root = self._resolve_project(project_key)
        single_source = self._single_project_source(project_root)
        if single_source is not None and relative_path.replace("\\", "/") != single_source.name:
            raise ProjectServiceError("单文件项目只能保存主源文件")
        target, normalized = self._resolve_project_path(project_key, relative_path, allow_missing=True)
        if single_source is None:
            self._validate_package_path_policy(project_root, normalized)
        if target.exists() and not target.is_file():
            raise ProjectServiceError("目标不是文件")
        if expected_mtime is not None and target.exists() and abs(target.stat().st_mtime - expected_mtime) > 1e-6:
            raise ProjectServiceError("文件已发生变化，请刷新后重试")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.parent / f".{target.name}.save-{uuid.uuid4().hex[:12]}"
        try:
            temporary.write_bytes(content.encode("utf-8"))
            temporary.replace(target)
        except Exception:
            if temporary.exists():
                temporary.unlink()
            raise
        return self.read_file(project_key, normalized)

    def _require_package_project(self, project_key: str) -> Path:
        project_root = self._resolve_project(project_key)
        if self._project_type(project_root) in _SINGLE_PROJECT_TYPES:
            raise ProjectServiceError("单文件项目不支持新增、上传、重命名或移动内部文件")
        return project_root

    def _validate_package_path_policy(self, project_root: Path, relative_path: str, *, is_directory: bool = False) -> None:
        """在写入前执行项目类型和 Blockly 生成路径约束。"""

        normalized = normalize_package_path(relative_path)
        path = PurePosixPath(normalized)
        project_type = self._project_type(project_root)
        inside_blockly = bool(path.parts and path.parts[0].casefold() == "blockly")
        if inside_blockly and project_type != "blockly-package":
            raise ProjectServiceError(f"{project_type} 项目不支持 Blockly 源文件或目录")
        if project_type == "maa" and not is_directory and path.suffix.casefold() == ".lua":
            raise ProjectServiceError("Maa 自动化项目不支持 Lua 脚本")
        if project_type != "blockly-package" or is_directory:
            return

        if path.suffix.casefold() == ".xml" and not inside_blockly:
            raise ProjectServiceError("Blockly XML 必须创建在 blockly/ 目录内")
        if inside_blockly and path.suffix.casefold() != ".xml":
            raise ProjectServiceError("blockly/ 目录只允许 Blockly .xml 源文件")

        if inside_blockly and path.suffix.casefold() == ".xml":
            generated_path = blockly_source_to_script_path(normalized)
            generated_target = project_root / Path(*PurePosixPath(generated_path).parts)
            if generated_target.exists():
                raise ProjectServiceError(f"Blockly 生成 Lua 与现有文件冲突: {generated_path}")
            return

        if path.parts and path.parts[0].casefold() == "scripts" and path.suffix.casefold() == ".lua":
            source_relative = PurePosixPath("blockly", *path.parts[1:]).with_suffix(".xml")
            source_target = project_root / Path(*source_relative.parts)
            if source_target.exists():
                raise ProjectServiceError(f"Lua 文件与 Blockly 生成目标冲突: {source_relative.as_posix()} -> {normalized}")

    def _validate_moved_tree_policy(self, project_root: Path, source: Path, destination_path: str) -> None:
        """移动目录时按目标相对路径校验其中每个文件。"""

        self._validate_package_path_policy(project_root, destination_path, is_directory=source.is_dir())
        if not source.is_dir():
            return
        destination = PurePosixPath(destination_path)
        for child in source.rglob("*"):
            if not child.is_file():
                continue
            mapped = destination / PurePosixPath(child.relative_to(source).as_posix())
            self._validate_package_path_policy(project_root, mapped.as_posix())

    def _module_key_for_project_path(self, relative_path: str, *, is_directory: bool) -> str | None:
        path = PurePosixPath(relative_path)
        if not path.parts or path.parts[0] not in {"scripts", "blockly"}:
            return None
        relative = PurePosixPath(*path.parts[1:])
        if not relative.parts:
            return ""
        if is_directory:
            return relative.as_posix()
        expected_suffix = ".lua" if path.parts[0] == "scripts" else ".xml"
        return relative.with_suffix("").as_posix() if path.suffix.casefold() == expected_suffix else None

    def _remap_blockly_module_references(
        self,
        project_root: Path,
        source_path: str,
        destination_path: str,
        *,
        is_directory: bool,
    ) -> None:
        """移动模块后同步 Blockly XML 内持久化的模块键和虚拟文件路径。"""

        if self._project_type(project_root) != "blockly-package":
            return
        old_key = self._module_key_for_project_path(source_path, is_directory=is_directory)
        new_key = self._module_key_for_project_path(destination_path, is_directory=is_directory)
        if old_key is None or new_key is None or old_key == new_key:
            return

        field_pattern = re.compile(
            r'(<field\b[^>]*\bname=(["\'])(MODULE_VALUE|FILE_VALUE)\2[^>]*>)(.*?)(</field>)',
            re.DOTALL,
        )
        originals: dict[Path, str] = {}
        try:
            for xml_path in sorted((project_root / "blockly").rglob("*.xml")):
                source = xml_path.read_text(encoding="utf-8")

                def replace_field(match: re.Match[str]) -> str:
                    value = html.unescape(match.group(4)).strip()
                    if match.group(3) == "FILE_VALUE" and value.startswith("scripts/") and value.endswith(".lua"):
                        key = value[len("scripts/"):-len(".lua")]
                        remapped = self._remap_module_key(key, old_key, new_key, is_directory)
                        value = f"scripts/{remapped}.lua"
                    elif match.group(3) == "MODULE_VALUE":
                        value = self._remap_module_key(value, old_key, new_key, is_directory)
                    return f"{match.group(1)}{html.escape(value, quote=False)}{match.group(5)}"

                updated = field_pattern.sub(replace_field, source)
                if updated == source:
                    continue
                originals[xml_path] = source
                temporary = xml_path.parent / f".{xml_path.name}.module-remap-{uuid.uuid4().hex[:8]}"
                temporary.write_text(updated, encoding="utf-8", newline="")
                temporary.replace(xml_path)
        except Exception as exc:
            for xml_path, source in originals.items():
                xml_path.write_text(source, encoding="utf-8", newline="")
            raise ProjectServiceError(f"同步 Blockly 模块引用失败: {exc}") from exc

    def _remap_module_key(self, value: str, old_key: str, new_key: str, is_directory: bool) -> str:
        if value == old_key:
            return new_key
        if is_directory and old_key and value.startswith(f"{old_key}/"):
            return f"{new_key}{value[len(old_key):]}"
        return value

    def validate(self, project_key: str) -> list[ProjectDiagnostic]:
        project_root = self._resolve_project(project_key)
        if self._project_type(project_root) in _SINGLE_PROJECT_TYPES:
            if self._single_project_source(project_root) is None:
                return [ProjectDiagnostic(code="single.source", message="单文件项目缺少同名源文件")]
            return []
        _, diagnostics, _ = validate_project(project_root)
        return diagnostics

    def get_module_index(self, project_key: str) -> list[dict[str, object]]:
        """返回当前项目可静态识别的模块与导出函数。"""

        project_root = self._resolve_project(project_key)
        project_type = self._project_type(project_root)
        if project_type not in {"lua-package", "blockly-package"}:
            return []
        return build_project_module_index(project_root, project_type)

    def prepare_debug_target(
        self,
        project_key: str,
        *,
        entry_path: str = "",
        source_overrides: Mapping[str, str] | None = None,
    ) -> ProjectDebugTarget:
        """校验调试入口，并把前端源码快照限制在当前项目的 Lua 模块空间内。"""

        project_root = self._resolve_project(project_key)
        project_type = self._project_type(project_root)
        if project_type == "maa":
            raise ProjectServiceError("Maa 项目请使用 Pipeline 调试入口")

        source = self._single_project_source(project_root)
        if project_type in _SINGLE_PROJECT_TYPES:
            if source is None:
                raise ProjectServiceError("单文件项目缺少同名源文件")
            if project_type == "lua-file":
                resolved_entry = source.name
                script_file = source
            else:
                resolved_entry = f"{source.stem}.lua"
                script_file = project_root / resolved_entry
            if entry_path:
                try:
                    requested_entry = normalize_package_path(entry_path)
                except ValueError as exc:
                    raise ProjectServiceError(str(exc)) from exc
                if requested_entry != resolved_entry:
                    raise ProjectServiceError("单文件项目只能调试主文件")
            if source_overrides:
                raise ProjectServiceError("单文件调试不接受额外模块覆盖")
            return ProjectDebugTarget(
                project_key=project_key,
                project_type=project_type,
                project_root=str(project_root.resolve()),
                entry_path=resolved_entry,
                script_path=str(script_file.resolve()),
            )

        if project_type not in {"lua-package", "blockly-package"}:
            raise ProjectServiceError(f"项目类型不支持脚本调试: {project_type}")
        manifest = load_project_manifest(project_root)
        default_entry = next(
            (
                entry.script or (blockly_source_to_script_path(entry.blockly) if entry.blockly else "")
                for entry in manifest.entrypoints.values()
                if entry.script or entry.blockly
            ),
            "",
        )
        if not (entry_path or default_entry):
            raise ProjectServiceError("项目没有可调试的脚本入口")
        try:
            resolved_entry = normalize_package_path(entry_path or default_entry)
        except ValueError as exc:
            raise ProjectServiceError(str(exc)) from exc
        if not resolved_entry.startswith("scripts/") or not resolved_entry.casefold().endswith(".lua"):
            raise ProjectServiceError("调试入口必须是 scripts/ 内的 Lua 文件")

        normalized_overrides: dict[str, str] = {}
        for raw_path, raw_source in (source_overrides or {}).items():
            try:
                normalized_path = normalize_package_path(raw_path)
            except ValueError as exc:
                raise ProjectServiceError(str(exc)) from exc
            if not normalized_path.startswith("scripts/") or not normalized_path.casefold().endswith(".lua"):
                raise ProjectServiceError(f"调试源码覆盖仅允许 scripts/ 内的 Lua 文件: {normalized_path}")
            normalized_overrides[normalized_path] = str(raw_source)
        return ProjectDebugTarget(
            project_key=project_key,
            project_type=project_type,
            project_root=str(project_root.resolve()),
            entry_path=resolved_entry,
            script_path=str((project_root / PurePosixPath(resolved_entry)).resolve()),
            source_overrides=normalized_overrides,
        )

    def get_template_config_root(self, project_key: str) -> Path:
        """返回项目模板调试配置的 Web 私有目录，不把配置写进可打包项目。"""

        self._resolve_project(project_key)
        return (self.artifact_root.parent / "settings" / "templates" / project_key).resolve()

    def prepare_pipeline_debug_target(
        self,
        project_key: str,
        *,
        descriptor_path: str = "",
    ) -> ProjectPipelineDebugTarget:
        """读取 Maa 项目声明的调试描述文件，不允许把任意宿主路径交给 Pipeline。"""

        project_root = self._resolve_project(project_key)
        if self._project_type(project_root) != "maa":
            raise ProjectServiceError("只有 Maa 项目可以使用 Pipeline 调试入口")
        manifest = load_project_manifest(project_root)
        default_descriptor = next((entry.maa for entry in manifest.entrypoints.values() if entry.maa), "")
        if not (descriptor_path or default_descriptor):
            raise ProjectServiceError("Maa 项目没有调试描述文件")
        try:
            normalized = normalize_package_path(descriptor_path or default_descriptor)
        except ValueError as exc:
            raise ProjectServiceError(str(exc)) from exc
        if not normalized.startswith("tasks/") or not normalized.casefold().endswith(".json"):
            raise ProjectServiceError("Maa 调试描述文件必须位于 tasks/ 内")
        descriptor, _ = self._resolve_project_path(project_key, normalized)
        try:
            payload = json.loads(descriptor.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ProjectServiceError(f"Maa 调试描述文件无效: {exc}") from exc
        if not isinstance(payload, dict):
            raise ProjectServiceError("Maa 调试描述文件必须是 JSON 对象")
        entry = str(payload.get("entry") or "").strip()
        if not entry:
            raise ProjectServiceError("Maa 调试描述文件缺少 entry")
        override = payload.get("override") or {}
        if not isinstance(override, dict):
            raise ProjectServiceError("Maa 调试 override 必须是对象")
        return ProjectPipelineDebugTarget(
            project_key=project_key,
            descriptor_path=normalized,
            project_path=str(project_root.resolve()),
            entry=entry,
            override=override,
        )

    def build(
        self,
        project_key: str,
        *,
        generated_lua: str | None = None,
        generated_from: str | None = None,
        generated_modules: Mapping[str, str] | None = None,
    ) -> ProjectBuildResult:
        project_root = self._resolve_project(project_key)
        project_type = self._project_type(project_root)
        if project_type in _SINGLE_PROJECT_TYPES:
            source = self._single_project_source(project_root)
            if source is None:
                raise ProjectServiceError("单文件项目缺少同名源文件")
            if project_type == "blockly-file":
                if generated_from != source.name or not str(generated_lua or "").strip():
                    raise ProjectServiceError("请先打开并校验 Blockly 主文件，再导出 Lua")
                content = str(generated_lua).encode("utf-8")
            else:
                content = source.read_bytes()

            build_id = uuid.uuid4().hex[:16]
            output_dir = self.artifact_root / project_key / build_id
            output_dir.mkdir(parents=True, exist_ok=False)
            output_path = output_dir / f"{project_root.name}.lua"
            output_path.write_bytes(content)
            result = ProjectBuildResult(
                build_id=build_id,
                project_key=project_key,
                filename=output_path.name,
                artifact_path=str(output_path),
                size=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
                files=[source.name],
            )
            self._build_artifacts[(project_key, build_id)] = output_path
            return result

        if project_type == "blockly-package":
            manifest = load_project_manifest(project_root)
            blockly_paths = {entry.blockly for entry in manifest.entrypoints.values() if entry.blockly}
            if not generated_modules and generated_from not in blockly_paths:
                raise ProjectServiceError("请先打开 Blockly 主入口，再打包项目")
        try:
            data = build_project_package(
                project_root,
                self.artifact_root,
                project_key,
                generated_lua=generated_lua,
                generated_lua_by_source=generated_modules,
            )
        except Exception as exc:
            if hasattr(exc, "diagnostics"):
                raise ProjectServiceError({"message": str(exc), "diagnostics": [item.model_dump() for item in exc.diagnostics]}) from exc
            raise ProjectServiceError(str(exc)) from exc
        result = ProjectBuildResult.model_validate(data)
        self._build_artifacts[(project_key, result.build_id)] = Path(result.artifact_path)
        return result

    def get_build_artifact(self, project_key: str, build_id: str) -> tuple[Path, str]:
        """按 project key 和 build id 定位宿主机管理的构建产物。"""

        self._resolve_project(project_key)
        normalized_id = str(build_id or "").strip()
        if not re.fullmatch(r"[0-9a-f]{16}", normalized_id):
            raise ProjectServiceError("构建 ID 无效")
        artifact = self._build_artifacts.get((project_key, normalized_id))
        if artifact is None or not artifact.is_file():
            raise ProjectServiceError("构建产物不存在")
        return artifact, artifact.name
