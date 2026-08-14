"""Web 构建产物的发现、校验与运行准备。"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Literal

import yaml
from pydantic import BaseModel, Field

from mluascript.shared.config import GlobalConfig, config

from .manager import WorkspaceManager
from .package_builder import normalize_package_path
from .project_models import ProjectManifest

if TYPE_CHECKING:
    from .project_service import ProjectService


MAX_README_BYTES = 512 * 1024


class ArtifactServiceError(ValueError):
    """构建产物不可发现、不可校验或不可运行。"""


@dataclass(slots=True)
class ArtifactTemplateSource:
    """单个构建入口的模板源码；一个入口只允许解析一个模板块。"""

    artifact: "RunnableArtifact"
    script_path: str
    code: str


def cleanup_artifact_runtime_dir(raw_path: str | Path | None) -> bool:
    """仅删除由产物服务创建的任务运行目录。"""

    if not raw_path:
        return False
    target = Path(raw_path).resolve()
    parent = target.parent
    is_owned_runtime = (
        target.name.startswith("package-")
        and parent.name == "tasks"
        and parent.parent.name == "runtime"
        and parent.parent.parent.name == ".mluascript_web"
    )
    if not is_owned_runtime:
        return False
    shutil.rmtree(target, ignore_errors=True)
    return not target.exists()


class RunnableArtifact(BaseModel):
    """任务管理可展示和启动的不可变运行入口。"""

    id: str
    kind: Literal["package", "maa", "lua"]
    name: str
    path: str
    mtime: float
    description: str = ""
    author: str = ""
    version: str = ""
    package_id: str = ""
    project_type: str = ""
    entrypoint: str = ""
    source: Literal["build", "configured"] = "build"
    run_mode: Literal["artifact", "lua"] = "artifact"
    has_readme: bool = False
    artifact_path: str = Field(exclude=True)


class ArtifactReadme(BaseModel):
    """已通过包摘要校验的 README 文档。"""

    artifact_id: str
    name: str
    path: str
    markdown: str


@dataclass(slots=True)
class PreparedArtifactRun:
    mode: Literal["script", "pipeline"]
    artifact: RunnableArtifact
    script_path: str = ""
    code: str = ""
    entry: str = ""
    override: dict[str, object] | None = None
    project_path: str = ""
    cleanup_dir: str | None = None

    @property
    def summary(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact.id,
            "artifact_path": self.artifact.path,
            "package_id": self.artifact.package_id,
            "package_version": self.artifact.version,
            "entrypoint": self.artifact.entrypoint,
            "project_type": self.artifact.project_type,
        }

    def cleanup(self) -> None:
        cleanup_artifact_runtime_dir(self.cleanup_dir)


class ArtifactService:
    """以 builds 为默认部署目录，同时保留显式 scripts_path。"""

    def __init__(
        self,
        builds_root: str | Path,
        *,
        runtime_root: str | Path | None = None,
        workspace_manager: WorkspaceManager | None = None,
        project_service: ProjectService | None = None,
    ) -> None:
        self.builds_root = Path(builds_root).resolve()
        self.runtime_root = Path(runtime_root or (self.builds_root.parent / "runtime" / "tasks")).resolve()
        self.workspace_manager = workspace_manager or WorkspaceManager(self.builds_root.parent.parent)
        self.project_service = project_service
        self._manifest_cache: dict[Path, tuple[int, int, ProjectManifest | None, str]] = {}
        self._readme_presence_cache: dict[Path, tuple[int, int, bool]] = {}

    def list_artifacts(self) -> list[RunnableArtifact]:
        packages = self._latest_packages()
        single_files = self._latest_single_file_builds()
        configured = self._configured_scripts()
        items = [*packages, *single_files, *configured]
        return sorted(items, key=lambda item: (item.kind, item.name.casefold(), item.version, item.entrypoint))

    def get_artifact(self, artifact_id: str) -> RunnableArtifact:
        for artifact in self.list_artifacts():
            if artifact.id == artifact_id:
                return artifact
        raise ArtifactServiceError("运行产物不存在或已被更新，请刷新任务列表")

    def get_template_source(self, artifact_id: str) -> ArtifactTemplateSource:
        """读取并校验当前构建入口 Lua，供模板预览和模板运行复用。"""

        artifact = self.get_artifact(artifact_id)
        if artifact.kind == "maa":
            raise ArtifactServiceError("Maa 构建包不支持 Lua 模板")
        if artifact.kind == "package":
            manifest = self._read_package_manifest(Path(artifact.artifact_path))
            entry = manifest.entrypoints.get(artifact.entrypoint)
            if entry is None or not entry.script:
                raise ArtifactServiceError("构建包入口没有生成后的 Lua 脚本")
            code = self._read_verified_package_text(
                Path(artifact.artifact_path),
                entry.script,
                max_bytes=4 * 1024 * 1024,
            )
            return ArtifactTemplateSource(artifact=artifact, script_path=entry.script, code=code)
        path = Path(artifact.artifact_path)
        try:
            code = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ArtifactServiceError(f"读取 Lua 产物失败: {exc}") from exc
        return ArtifactTemplateSource(artifact=artifact, script_path=path.name, code=code)

    def template_config_dir(self, artifact_id: str) -> Path:
        """返回按构建产物隔离的模板配置目录，不修改包内容。"""

        self.get_artifact(artifact_id)
        return (self.builds_root.parent / "settings" / "templates" / "artifacts" / artifact_id).resolve()

    def prepare_run(self, artifact_id: str) -> PreparedArtifactRun:
        artifact = self.get_artifact(artifact_id)
        if artifact.kind == "lua":
            path = Path(artifact.artifact_path)
            try:
                code = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                raise ArtifactServiceError(f"读取 Lua 产物失败: {exc}") from exc
            return PreparedArtifactRun(mode="script", artifact=artifact, script_path=str(path), code=code)
        return self._prepare_package(artifact)

    def read_readme(self, artifact_id: str) -> ArtifactReadme:
        """读取包根目录 README.md；单文件构建产物不提供内嵌文档。"""

        artifact = self.get_artifact(artifact_id)
        if artifact.kind == "lua":
            raise ArtifactServiceError("单文件构建产物不包含包 README")
        if not artifact.has_readme:
            raise ArtifactServiceError("构建包没有 README.md")
        markdown = self._read_verified_package_text(
            Path(artifact.artifact_path),
            "README.md",
            max_bytes=MAX_README_BYTES,
        )
        return ArtifactReadme(
            artifact_id=artifact.id,
            name=artifact.name,
            path=artifact.path,
            markdown=markdown,
        )

    def _latest_packages(self) -> list[RunnableArtifact]:
        latest: dict[tuple[str, str], tuple[Path, ProjectManifest]] = {}
        if not self.builds_root.is_dir():
            self._manifest_cache.clear()
            return []
        package_paths = sorted(self.builds_root.rglob("*.mlspkg"))
        current_paths = {path.resolve() for path in package_paths}
        self._manifest_cache = {
            path: entry for path, entry in self._manifest_cache.items() if path in current_paths
        }
        for path in package_paths:
            try:
                manifest = self._read_package_manifest(path)
            except ArtifactServiceError:
                continue
            key = (manifest.package.id, manifest.package.version)
            current = latest.get(key)
            if current is None or path.stat().st_mtime > current[0].stat().st_mtime:
                latest[key] = (path, manifest)

        items: list[RunnableArtifact] = []
        for path, manifest in latest.values():
            for entrypoint, entry in manifest.entrypoints.items():
                entry_name = entry.name or entrypoint
                item_name = manifest.package.name if len(manifest.entrypoints) == 1 else f"{manifest.package.name} · {entry_name}"
                items.append(
                    RunnableArtifact(
                        id=self._artifact_id("package", path, entrypoint),
                        kind="maa" if manifest.project_type == "maa" else "package",
                        name=item_name,
                        path=self._display_path(path),
                        mtime=path.stat().st_mtime,
                        description=manifest.package.description,
                        author=manifest.package.author,
                        version=manifest.package.version,
                        package_id=manifest.package.id,
                        project_type=manifest.project_type,
                        entrypoint=entrypoint,
                        source="build",
                        run_mode="artifact",
                        has_readme=self._package_has_readme(path),
                        artifact_path=str(path),
                    )
                )
        return items

    def _latest_single_file_builds(self) -> list[RunnableArtifact]:
        latest: dict[str, Path] = {}
        if not self.builds_root.is_dir():
            return []
        for path in sorted(self.builds_root.rglob("*.lua")):
            relative = path.relative_to(self.builds_root)
            parts = relative.parts
            group = parts[0] if len(parts) >= 3 and re.fullmatch(r"[0-9a-f]{16}", parts[1]) else relative.as_posix()
            current = latest.get(group)
            if current is None or path.stat().st_mtime > current.stat().st_mtime:
                latest[group] = path
        return [
            self._lua_artifact(
                path,
                source="build",
                run_mode="artifact",
                project_type=self._single_file_project_type(path),
            )
            for path in latest.values()
        ]

    def _single_file_project_type(self, path: Path) -> str:
        """从构建目录的项目 key 恢复单文件项目的源类型。"""

        if self.project_service is None:
            return ""
        try:
            relative = path.relative_to(self.builds_root)
        except ValueError:
            return ""
        if len(relative.parts) < 3:
            return ""
        project_key = relative.parts[0]
        try:
            project = self.project_service.get_project(project_key)
        except ValueError:
            return ""
        return project.project_type if project.project_type in {"lua-file", "blockly-file"} else ""

    def _configured_scripts(self) -> list[RunnableArtifact]:
        # 隔离测试或嵌入式工作区不继承宿主进程的外部脚本目录。
        if self.workspace_manager.root_dir != Path.cwd().resolve():
            return []
        try:
            configured_paths = list(config.get(GlobalConfig).scripts_path)
        except Exception:
            configured_paths = []
        items: list[RunnableArtifact] = []
        seen: set[Path] = set()
        for raw_root in configured_paths:
            root = Path(str(raw_root)).expanduser()
            root = root.resolve() if root.is_absolute() else (self.workspace_manager.root_dir / root).resolve()
            if not root.is_dir():
                continue
            for path in sorted(root.glob("*.lua")):
                resolved = path.resolve()
                if resolved in seen or not resolved.is_file():
                    continue
                seen.add(resolved)
                items.append(self._lua_artifact(resolved, source="configured", run_mode="artifact"))
        return items

    def _lua_artifact(
        self,
        path: Path,
        *,
        source: Literal["build", "configured"],
        run_mode: Literal["artifact", "lua"],
        project_type: str = "",
    ) -> RunnableArtifact:
        return RunnableArtifact(
            id=self._artifact_id(source, path),
            kind="lua",
            name=path.name,
            path=self._display_path(path),
            mtime=path.stat().st_mtime,
            project_type=project_type,
            source=source,
            run_mode=run_mode,
            artifact_path=str(path),
        )

    def _prepare_package(self, artifact: RunnableArtifact) -> PreparedArtifactRun:
        package_path = Path(artifact.artifact_path)
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        run_root = Path(tempfile.mkdtemp(prefix="package-", dir=self.runtime_root))
        try:
            self._verify_and_extract(package_path, run_root)
            manifest = self._load_extracted_manifest(run_root)
            entrypoint = manifest.entrypoints.get(artifact.entrypoint)
            if entrypoint is None:
                raise ArtifactServiceError(f"包入口不存在: {artifact.entrypoint}")

            if manifest.project_type in {"lua-package", "blockly-package"}:
                if not entrypoint.script:
                    raise ArtifactServiceError("包入口没有生成后的 Lua 脚本")
                script_path = self._safe_extracted_path(run_root, entrypoint.script)
                code = script_path.read_text(encoding="utf-8")
                return PreparedArtifactRun(
                    mode="script",
                    artifact=artifact,
                    script_path=str(script_path),
                    code=code,
                    project_path=str(run_root),
                    cleanup_dir=str(run_root),
                )

            if manifest.project_type == "maa":
                if not entrypoint.maa:
                    raise ArtifactServiceError("Maa 包入口缺少任务描述符")
                descriptor_path = self._safe_extracted_path(run_root, entrypoint.maa)
                descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
                if not isinstance(descriptor, dict) or not str(descriptor.get("entry") or "").strip():
                    raise ArtifactServiceError("Maa 任务描述符缺少 entry")
                raw_override = descriptor.get("override")
                if raw_override is not None and not isinstance(raw_override, dict):
                    raise ArtifactServiceError("Maa 任务描述符 override 必须是对象")
                return PreparedArtifactRun(
                    mode="pipeline",
                    artifact=artifact,
                    entry=str(descriptor["entry"]),
                    override=dict(raw_override or {}),
                    project_path=str(run_root),
                    cleanup_dir=str(run_root),
                )
            raise ArtifactServiceError(f"不支持运行的包类型: {manifest.project_type}")
        except Exception:
            shutil.rmtree(run_root, ignore_errors=True)
            raise

    def _verify_and_extract(self, package_path: Path, target_root: Path) -> None:
        try:
            with zipfile.ZipFile(package_path) as archive:
                files: dict[str, zipfile.ZipInfo] = {}
                for info in archive.infolist():
                    if info.is_dir():
                        continue
                    normalized = normalize_package_path(info.filename)
                    if normalized != info.filename or normalized in files:
                        raise ArtifactServiceError(f"包内文件路径无效或重复: {info.filename}")
                    files[normalized] = info
                checksum_info = files.pop("META-INF/files.sha256", None)
                if checksum_info is None:
                    raise ArtifactServiceError("包缺少 META-INF/files.sha256")
                expected = self._parse_checksums(archive.read(checksum_info).decode("utf-8"))
                if set(expected) != set(files):
                    raise ArtifactServiceError("包文件列表与摘要清单不一致")

                for relative, info in files.items():
                    target = self._safe_extracted_path(target_root, relative, allow_missing=True)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    digest = hashlib.sha256()
                    with archive.open(info) as source, target.open("xb") as output:
                        while chunk := source.read(1024 * 1024):
                            digest.update(chunk)
                            output.write(chunk)
                    if digest.hexdigest() != expected[relative]:
                        raise ArtifactServiceError(f"包文件摘要校验失败: {relative}")
        except (OSError, UnicodeError, zipfile.BadZipFile, ValueError) as exc:
            if isinstance(exc, ArtifactServiceError):
                raise
            raise ArtifactServiceError(f"读取构建包失败: {exc}") from exc

    def _read_verified_package_text(self, package_path: Path, relative: str, *, max_bytes: int) -> str:
        """校验归档文件表与目标摘要后读取一个 UTF-8 文本文件。"""

        try:
            with zipfile.ZipFile(package_path) as archive:
                files: dict[str, zipfile.ZipInfo] = {}
                for info in archive.infolist():
                    if info.is_dir():
                        continue
                    normalized = normalize_package_path(info.filename)
                    if normalized != info.filename or normalized in files:
                        raise ArtifactServiceError(f"包内文件路径无效或重复: {info.filename}")
                    files[normalized] = info
                checksum_info = files.pop("META-INF/files.sha256", None)
                if checksum_info is None:
                    raise ArtifactServiceError("包缺少 META-INF/files.sha256")
                expected = self._parse_checksums(archive.read(checksum_info).decode("utf-8"))
                if set(expected) != set(files):
                    raise ArtifactServiceError("包文件列表与摘要清单不一致")
                info = files.get(relative)
                if info is None:
                    raise ArtifactServiceError(f"构建包没有 {relative}")
                if info.file_size > max_bytes:
                    raise ArtifactServiceError(f"{relative} 超过 {max_bytes // 1024} KiB 限制")
                content = archive.read(info)
                if hashlib.sha256(content).hexdigest() != expected[relative]:
                    raise ArtifactServiceError(f"包文件摘要校验失败: {relative}")
                return content.decode("utf-8")
        except (OSError, UnicodeError, zipfile.BadZipFile, ValueError) as exc:
            if isinstance(exc, ArtifactServiceError):
                raise
            raise ArtifactServiceError(f"读取构建包失败: {exc}") from exc

    def _package_has_readme(self, path: Path) -> bool:
        resolved = path.resolve()
        stat = resolved.stat()
        cached = self._readme_presence_cache.get(resolved)
        if cached and cached[0] == stat.st_mtime_ns and cached[1] == stat.st_size:
            return cached[2]
        try:
            with zipfile.ZipFile(resolved) as archive:
                present = any(not info.is_dir() and info.filename == "README.md" for info in archive.infolist())
        except (OSError, zipfile.BadZipFile):
            present = False
        self._readme_presence_cache[resolved] = (stat.st_mtime_ns, stat.st_size, present)
        return present

    def _read_package_manifest(self, path: Path) -> ProjectManifest:
        resolved = path.resolve()
        stat = resolved.stat()
        cached = self._manifest_cache.get(resolved)
        if cached and cached[0] == stat.st_mtime_ns and cached[1] == stat.st_size:
            if cached[2] is None:
                raise ArtifactServiceError(cached[3])
            return cached[2]
        try:
            with zipfile.ZipFile(resolved) as archive:
                raw = yaml.safe_load(archive.read("mluascript.yaml").decode("utf-8"))
            manifest = ProjectManifest.model_validate(raw)
        except Exception as exc:
            message = f"读取包清单失败: {exc}"
            self._manifest_cache[resolved] = (stat.st_mtime_ns, stat.st_size, None, message)
            raise ArtifactServiceError(message) from exc
        if manifest.schema_ != "mluascript.package/v1":
            message = f"不支持的包 schema: {manifest.schema_}"
            self._manifest_cache[resolved] = (stat.st_mtime_ns, stat.st_size, None, message)
            raise ArtifactServiceError(message)
        self._manifest_cache[resolved] = (stat.st_mtime_ns, stat.st_size, manifest, "")
        return manifest

    def _load_extracted_manifest(self, root: Path) -> ProjectManifest:
        try:
            raw = yaml.safe_load((root / "mluascript.yaml").read_text(encoding="utf-8"))
            manifest = ProjectManifest.model_validate(raw)
        except Exception as exc:
            raise ArtifactServiceError(f"运行包清单无效: {exc}") from exc
        if manifest.schema_ != "mluascript.package/v1":
            raise ArtifactServiceError(f"不支持的包 schema: {manifest.schema_}")
        return manifest

    @staticmethod
    def _parse_checksums(content: str) -> dict[str, str]:
        checksums: dict[str, str] = {}
        for line in content.splitlines():
            match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
            if not match:
                raise ArtifactServiceError("包摘要清单格式无效")
            relative = normalize_package_path(match.group(2))
            if relative in checksums:
                raise ArtifactServiceError(f"包摘要路径重复: {relative}")
            checksums[relative] = match.group(1)
        return checksums

    @staticmethod
    def _safe_extracted_path(root: Path, relative: str, *, allow_missing: bool = False) -> Path:
        normalized = normalize_package_path(relative)
        target = (root / Path(*PurePosixPath(normalized).parts)).resolve()
        try:
            target.relative_to(root.resolve())
        except ValueError as exc:
            raise ArtifactServiceError(f"包路径超出运行目录: {relative}") from exc
        if not allow_missing and not target.is_file():
            raise ArtifactServiceError(f"包文件不存在: {relative}")
        return target

    @staticmethod
    def _artifact_id(source: str, path: Path, entrypoint: str = "") -> str:
        identity = f"{source}\0{path.resolve()}\0{path.stat().st_size}\0{path.stat().st_mtime_ns}\0{entrypoint}"
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]

    def _display_path(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.builds_root.parent.parent).as_posix()
        except ValueError:
            return str(path.resolve())


__all__ = [
    "ArtifactService",
    "ArtifactServiceError",
    "ArtifactReadme",
    "ArtifactTemplateSource",
    "PreparedArtifactRun",
    "RunnableArtifact",
    "cleanup_artifact_runtime_dir",
]
