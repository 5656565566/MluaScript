from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

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
            for file in sorted(base_dir.glob("*.lua")):
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
        config_file = root / "mluascript.project.yaml"
        templates_dir = root / "templates"
        resource_dir = root / "resource"
        if not resource_dir.exists():
            resource_dir = root

        return WorkspaceProject(
            project_id=str(root.relative_to(self.root_dir)).replace("\\", "/") if root != self.root_dir else root.name,
            name=root.name,
            root_dir=path_to_str(root),
            scripts_dir=path_to_str(root),
            resource_dir=path_to_str(resource_dir),
            templates_dir=path_to_str(templates_dir) if templates_dir.exists() else None,
            config_file=path_to_str(config_file) if config_file.exists() else None,
        )

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

    def build_script_run_locator(self, script_path: str) -> ScriptRunLocator:
        """为脚本运行构建项目/脚本/资源定位信息"""
        project = self.resolve_project(script_path)
        script = self.resolve_script_asset(script_path)
        project_root = Path(project.root_dir)
        resource_dir = Path(project.resource_dir)
        return ScriptRunLocator(
            project=project,
            script=script,
            project_root=project.root_dir,
            script_file=script.absolute_path,
            script_dir=path_to_str(Path(script.absolute_path).parent),
            working_dir=project.root_dir,
            resource_dir=project.resource_dir,
            templates_dir=project.templates_dir,
            resources=self._collect_resources(project.project_id, project_root, resource_dir),
        )

    def build_pipeline_run_locator(self, project_path: str) -> PipelineRunLocator:
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

        if project_root != resource_dir and project_root.exists():
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

        default_paths = [self.root_dir, self.root_dir / ".mluascript_web" / "lua"]

        for raw_path in [*configured_paths, *default_paths]:
            path_text = str(raw_path).strip()
            if not path_text:
                continue
            candidate = Path(path_text)
            resolved = candidate.resolve() if candidate.is_absolute() else (self.root_dir / candidate).resolve()
            if resolved not in roots:
                roots.append(resolved)

        return roots

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
        target = (self.root_dir / rel_path).resolve()
        try:
            target.relative_to(self.root_dir)
        except ValueError as exc:
            raise PermissionError(f"Access denied: {rel_path}") from exc
        return target


_global_workspace_manager = WorkspaceManager()


def get_workspace_manager() -> WorkspaceManager:
    return _global_workspace_manager
