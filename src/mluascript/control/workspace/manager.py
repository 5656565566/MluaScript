from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

import yaml

from mluascript.shared.config import GlobalConfig, config
from mluascript.shared.logging import logger
from .models import (
    PipelineRunLocator,
    ResourceAsset,
    ScriptAsset,
    ScriptInfo,
    ScriptRunLocator,
    WorkspaceProject,
    path_to_str,
)

_RESOURCE_SUFFIXES = {
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".bmp": "image",
    ".webp": "image",
    ".json": "data",
    ".yaml": "data",
    ".yml": "data",
    ".toml": "data",
    ".txt": "text",
}


class WorkspaceManager:
    """管理工作区文件、项目边界与运行定位信息"""

    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = (root_dir or Path.cwd()).resolve()

    def list_scripts(self) -> List[ScriptInfo]:
        """列出 scripts_path 指向目录顶层内的 lua 脚本文件"""
        items: List[ScriptInfo] = []
        seen: set[Path] = set()
        for base_dir in self._iter_script_roots():
            if not base_dir.exists() or not base_dir.is_dir():
                continue
            is_manifest_scripts_root = (base_dir.parent / "mluascript.yaml").is_file()
            is_web_projects_root = base_dir == (self.root_dir / ".mluascript_web" / "projects").resolve()
            candidates = base_dir.rglob("*.lua") if is_manifest_scripts_root or is_web_projects_root else base_dir.glob("*.lua")
            for file in sorted(candidates):
                resolved = file.resolve()
                if not resolved.is_file() or resolved in seen:
                    continue
                seen.add(resolved)
                items.append(
                    ScriptInfo(
                        name=resolved.name,
                        path=self._display_script_path(resolved, base_dir),
                        mtime=resolved.stat().st_mtime,
                    )
                )
        return sorted(items, key=lambda item: item.path)

    def read_script(self, rel_path: str) -> str:
        """读取指定的 lua 脚本"""
        target = self._resolve_workspace_path(rel_path)

        if not target.exists() or target.suffix.lower() != ".lua":
            raise FileNotFoundError(f"Script not found: {rel_path}")

        content = target.read_text(encoding="utf-8")
        logger.debug(f"Loaded script: {target}")
        return content

    def resolve_project(self, script_path: str) -> WorkspaceProject:
        """根据脚本路径解析其所属项目"""
        script_file = self._resolve_workspace_path(script_path)
        if not script_file.exists() or script_file.suffix.lower() != ".lua":
            raise FileNotFoundError(f"Script not found: {script_path}")
        return self.resolve_project_by_root(script_file.parent)

    def resolve_project_by_root(self, project_root: str | Path) -> WorkspaceProject:
        """根据项目根路径解析项目"""
        root = self._resolve_workspace_path(str(project_root)) if not isinstance(project_root, Path) or not project_root.is_absolute() else project_root.resolve()
        root = self._find_manifest_root(root)
        config_file = root / "mluascript.yaml"
        if not config_file.exists():
            config_file = root / "mluascript.project.yaml"
        templates_dir = root / "templates"
        scripts_dir = root / "scripts"
        if not scripts_dir.exists():
            scripts_dir = root
        resource_dir = root / "resources" / "maa"
        if not resource_dir.exists():
            resource_dir = root / "resource"
        if not resource_dir.exists():
            resource_dir = root

        return WorkspaceProject(
            project_id=str(root.relative_to(self.root_dir)).replace("\\", "/") if root != self.root_dir else root.name,
            name=root.name,
            root_dir=path_to_str(root),
            scripts_dir=path_to_str(scripts_dir),
            resource_dir=path_to_str(resource_dir),
            templates_dir=path_to_str(templates_dir) if templates_dir.exists() else None,
            config_file=path_to_str(config_file) if config_file.exists() else None,
            module_search_locked=self._module_search_locked(config_file),
        )

    def _module_search_locked(self, config_file: Path) -> bool:
        """仅可打包 Lua/Blockly 项目启用固定的 scripts 模块空间。"""

        if config_file.name != "mluascript.yaml" or not config_file.is_file():
            return False
        try:
            data = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError):
            return False
        return isinstance(data, dict) and data.get("type") in {"lua-package", "blockly-package"}

    def resolve_script_asset(self, script_path: str) -> ScriptAsset:
        """解析脚本资产信息"""
        script_file = self._resolve_workspace_path(script_path)
        project = self.resolve_project(script_path)
        project_root = Path(project.root_dir)
        return ScriptAsset(
            project_id=project.project_id,
            name=script_file.name,
            relative_path=str(script_file.relative_to(project_root)).replace("\\", "/"),
            absolute_path=path_to_str(script_file),
            mtime=script_file.stat().st_mtime,
            is_entry=True,
        )

    def build_script_run_locator(
        self,
        script_path: str,
        *,
        allow_missing: bool = False,
        source_overrides: dict[str, str] | None = None,
        cleanup_dir: str | None = None,
    ) -> ScriptRunLocator:
        """为脚本运行构建项目/脚本/资源定位信息"""
        normalized_path = str(script_path or "").strip()
        if normalized_path:
            script_file = self._resolve_workspace_path(normalized_path)
        else:
            # 内存代码没有保存路径时，虚拟文件名只用于确定运行目录和任务元数据。
            script_file = (self.root_dir / "untitled.lua").resolve()

        is_lua_file = script_file.suffix.lower() == ".lua"
        if not is_lua_file or (not allow_missing and not script_file.is_file()):
            raise FileNotFoundError(f"Script not found: {script_path}")

        project = self.resolve_project_by_root(script_file.parent)
        project_root = Path(project.root_dir)
        script = ScriptAsset(
            project_id=project.project_id,
            name=script_file.name,
            relative_path=str(script_file.relative_to(project_root)).replace("\\", "/"),
            absolute_path=path_to_str(script_file),
            mtime=script_file.stat().st_mtime if script_file.is_file() else 0.0,
        )
        resource_dir = Path(project.resource_dir)
        return ScriptRunLocator(
            project=project,
            script=script,
            project_root=project.root_dir,
            script_file=script.absolute_path,
            script_dir=project.scripts_dir,
            working_dir=project.root_dir,
            resource_dir=project.resource_dir,
            templates_dir=project.templates_dir,
            resources=self._collect_resources(project.project_id, project_root, resource_dir),
            source_overrides=dict(source_overrides or {}),
            cleanup_dir=cleanup_dir,
        )

    def build_pipeline_run_locator(self, project_path: str, *, cleanup_dir: str | None = None) -> PipelineRunLocator:
        """为 pipeline 运行构建项目/资源定位信息"""
        raw_path = self._resolve_workspace_path(project_path)
        root = raw_path.parent if raw_path.is_file() else raw_path
        project = self.resolve_project_by_root(root)
        project_root = Path(project.root_dir)
        resource_dir = Path(project.resource_dir)
        return PipelineRunLocator(
            project=project,
            project_root=project.root_dir,
            working_dir=project.root_dir,
            resource_dir=project.resource_dir,
            templates_dir=project.templates_dir,
            resources=self._collect_resources(project.project_id, project_root, resource_dir),
            cleanup_dir=cleanup_dir,
        )

    def _collect_resources(self, project_id: str, project_root: Path, resource_dir: Path) -> list[ResourceAsset]:
        resources: list[ResourceAsset] = []
        seen: set[Path] = set()

        for file in self._iter_resource_files(project_root, resource_dir):
            resolved = file.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            try:
                relative = resolved.relative_to(project_root)
            except ValueError:
                relative = Path(resolved.name)
            resources.append(
                ResourceAsset(
                    project_id=project_id,
                    relative_path=relative.as_posix(),
                    absolute_path=path_to_str(resolved),
                    kind=self._classify_resource(resolved),
                )
            )

        return sorted(resources, key=lambda item: item.relative_path)

    def _iter_resource_files(self, project_root: Path, resource_dir: Path) -> Iterable[Path]:
        if resource_dir.exists():
            yield from (file for file in resource_dir.rglob("*") if file.is_file() and file.suffix.lower() != ".lua")

        if project_root != resource_dir and project_root.exists() and not (project_root / "mluascript.yaml").is_file():
            yield from (
                file
                for file in project_root.iterdir()
                if file.is_file() and file.suffix.lower() != ".lua"
            )

    def _classify_resource(self, path: Path) -> str:
        return _RESOURCE_SUFFIXES.get(path.suffix.lower(), "file")

    def _iter_script_roots(self) -> list[Path]:
        roots: list[Path] = []
        try:
            global_cfg = config.get(GlobalConfig)
            configured_paths = list(global_cfg.scripts_path)
        except Exception:
            configured_paths = []

        default_paths = [
            self.root_dir,
            self.root_dir / ".mluascript_web" / "projects",
            self.root_dir / ".mluascript_web" / "lua",
        ]
        if self.root_dir.exists():
            for manifest_path in self.root_dir.rglob("mluascript.yaml"):
                scripts_dir = manifest_path.parent / "scripts"
                if scripts_dir.is_dir():
                    default_paths.append(scripts_dir)

        for raw_path in [*configured_paths, *default_paths]:
            path_text = str(raw_path).strip()
            if not path_text:
                continue
            candidate = Path(path_text)
            resolved = candidate.resolve() if candidate.is_absolute() else (self.root_dir / candidate).resolve()
            # 自定义 WorkspaceManager 通常用于隔离项目或测试；此时不应把全局配置中的
            # 宿主脚本目录意外带入当前工作区。默认全局 manager 仍保留原有配置行为。
            if self.root_dir != Path.cwd().resolve() and not self._is_under_workspace(resolved):
                continue
            if resolved not in roots:
                roots.append(resolved)

        return roots

    def _find_manifest_root(self, start: Path) -> Path:
        """向上查找标准项目 manifest，兼容无 manifest 的旧目录脚本。"""
        current = start.resolve()
        workspace_root = self.root_dir.resolve()
        while True:
            if (current / "mluascript.yaml").is_file() or (current / "mluascript.project.yaml").is_file():
                return current
            if current == workspace_root or current.parent == current:
                return start.resolve()
            try:
                current.relative_to(workspace_root)
            except ValueError:
                return start.resolve()
            current = current.parent

    def _display_script_path(self, resolved: Path, base_dir: Path) -> str:
        if base_dir.is_absolute() and not self._is_under_workspace(base_dir):
            return path_to_str(resolved)
        try:
            return str(resolved.relative_to(self.root_dir)).replace("\\", "/")
        except ValueError:
            return str(resolved.relative_to(base_dir)).replace("\\", "/")

    def _is_under_workspace(self, path: Path) -> bool:
        try:
            path.relative_to(self.root_dir)
            return True
        except ValueError:
            return False

    def _resolve_workspace_path(self, rel_path: str) -> Path:
        candidate = Path(rel_path)
        target = candidate.resolve() if candidate.is_absolute() else (self.root_dir / candidate).resolve()
        allowed_roots = [self.root_dir, *self._configured_script_roots()]
        if not any(self._is_relative_to(target, root) for root in allowed_roots):
            raise PermissionError(f"Access denied: {rel_path}")
        return target

    def _configured_script_roots(self) -> list[Path]:
        try:
            configured_paths = list(config.get(GlobalConfig).scripts_path)
        except Exception:
            configured_paths = []
        roots: list[Path] = []
        for raw_path in configured_paths:
            candidate = Path(str(raw_path)).expanduser()
            resolved = candidate.resolve() if candidate.is_absolute() else (self.root_dir / candidate).resolve()
            if resolved not in roots:
                roots.append(resolved)
        return roots

    @staticmethod
    def _is_relative_to(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False


_global_workspace_manager = WorkspaceManager()


def get_workspace_manager() -> WorkspaceManager:
    return _global_workspace_manager
