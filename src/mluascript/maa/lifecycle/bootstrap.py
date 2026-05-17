from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import sys
from pathlib import Path

from mluascript.shared.config import GlobalConfig, config
from mluascript.shared.config.manager import get_runtime_dir, resolve_path_from_runtime

from ..types import MaaPaths

_SHADOW_LIBRARY_CACHE: dict[tuple[Path, Path], tuple[Path, Path]] = {}


def _normalize_adb_path(raw: str) -> Path:
    path = Path(raw)
    if path.name.lower() in {"adb", "adb.exe"}:
        return path

    adb_name = "adb.exe" if platform.system().lower() == "windows" else "adb"
    return path / adb_name


def _resolve_packaged_maa_library_dir() -> Path | None:
    if getattr(sys, "frozen", False):
        bundle_root = getattr(sys, "_MEIPASS", None)
        if bundle_root:
            bundle_path = Path(bundle_root)
            for candidate in (bundle_path / "maa" / "bin", bundle_path / "maafw"):
                if candidate.exists():
                    return candidate
        return None

    spec = importlib.util.find_spec("maa")
    if spec is None or spec.origin is None:
        return None
    package_dir = Path(spec.origin).resolve().parent
    candidate = package_dir / "bin"
    if candidate.exists():
        return candidate
    return None


def _resolve_maa_shadow_root(base_dir: Path) -> Path:
    return base_dir / ".mluascript" / "maa"


def _resolve_external_plugin_dir(base_dir: Path) -> Path:
    return base_dir / "plugins"


def _copy_tree_contents(source: Path, target: Path) -> None:
    if not source.exists():
        return

    target.mkdir(parents=True, exist_ok=True)
    for entry in source.iterdir():
        destination = target / entry.name
        if entry.is_dir():
            shutil.copytree(entry, destination, dirs_exist_ok=True)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(entry, destination)


def _prepare_external_plugin_dir(source_library_dir: Path, runtime_dir: Path) -> Path:
    plugin_dir = _resolve_external_plugin_dir(runtime_dir)
    bundled_plugins = source_library_dir / "plugins"
    if plugin_dir.exists():
        return plugin_dir

    plugin_dir.mkdir(parents=True, exist_ok=True)
    if bundled_plugins.exists():
        _copy_tree_contents(bundled_plugins, plugin_dir)
    return plugin_dir


def _is_shadow_library_dir_ready(shadow_library_dir: Path, plugin_dir: Path) -> bool:
    return shadow_library_dir.exists() and (shadow_library_dir / "plugins").exists() and plugin_dir.exists()


def _build_shadow_library_dir(source_library_dir: Path, runtime_dir: Path) -> tuple[Path, Path]:
    cache_key = (source_library_dir.resolve(), runtime_dir.resolve())
    cached = _SHADOW_LIBRARY_CACHE.get(cache_key)
    if cached is not None:
        cached_shadow_library_dir, cached_plugin_dir = cached
        if _is_shadow_library_dir_ready(cached_shadow_library_dir, cached_plugin_dir):
            return cached

    plugin_dir = _prepare_external_plugin_dir(source_library_dir, runtime_dir)
    shadow_library_dir = _resolve_maa_shadow_root(runtime_dir) / "bin"
    if _is_shadow_library_dir_ready(shadow_library_dir, plugin_dir):
        _SHADOW_LIBRARY_CACHE[cache_key] = (shadow_library_dir, plugin_dir)
        return shadow_library_dir, plugin_dir

    shadow_library_dir.mkdir(parents=True, exist_ok=True)
    for entry in source_library_dir.iterdir():
        if entry.name == "plugins":
            continue
        destination = shadow_library_dir / entry.name
        if entry.is_dir():
            shutil.copytree(entry, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(entry, destination)

    shadow_plugins_dir = shadow_library_dir / "plugins"
    if shadow_plugins_dir.exists():
        shutil.rmtree(shadow_plugins_dir)
    shutil.copytree(plugin_dir, shadow_plugins_dir, dirs_exist_ok=True)
    _SHADOW_LIBRARY_CACHE[cache_key] = (shadow_library_dir, plugin_dir)
    return shadow_library_dir, plugin_dir


def _resolve_default_library_dir(base_dir: Path, global_cfg: GlobalConfig) -> tuple[Path, Path | None]:
    if global_cfg.maa_library_dir:
        return _build_shadow_library_dir(Path(global_cfg.maa_library_dir), base_dir)

    packaged_dir = _resolve_packaged_maa_library_dir()
    if packaged_dir is not None:
        return _build_shadow_library_dir(packaged_dir, base_dir)

    fallback_dir = base_dir / "maafw"
    plugin_dir = fallback_dir / "plugins" if fallback_dir.exists() else None
    return fallback_dir, plugin_dir


def resolve_maa_paths(root_dir: Path | None = None) -> MaaPaths:
    """根据当前配置解析 Maa 运行路径"""
    base_dir = root_dir or get_runtime_dir()
    global_cfg = config.get(GlobalConfig)

    library_dir, plugin_dir = _resolve_default_library_dir(base_dir, global_cfg)
    resource_dir = Path(global_cfg.maa_resource_dir) if global_cfg.maa_resource_dir else base_dir / "resource"
    model_dir = Path(global_cfg.maa_model_dir) if global_cfg.maa_model_dir else None
    
    adb_path = None
    if global_cfg.maa_adb_dir:
        adb_path = _normalize_adb_path(global_cfg.maa_adb_dir)
    elif platform.system().lower() == "linux":
        sys_adb = shutil.which("adb")
        if sys_adb:
            adb_path = Path(sys_adb)

    return MaaPaths(
        library_dir=library_dir,
        resource_dir=resource_dir,
        plugin_dir=plugin_dir,
        model_dir=model_dir,
        adb_path=adb_path,
    )


def prepare_maa_runtime_environment(root_dir: Path | None = None) -> MaaPaths:
    paths = resolve_maa_paths(root_dir)
    os.environ["MAAFW_BINARY_PATH"] = str(paths.library_dir)
    return paths


def configure_toolkit_options(paths: MaaPaths) -> dict[str, str]:
    """生成 Maa Toolkit 初始化参数"""
    options: dict[str, str] = {}
    if paths.adb_path is not None:
        options["adb_path"] = str(paths.adb_path)
    return options


def resolve_tasker_stdout_level():
    from maa.define import LoggingLevelEnum

    global_cfg = config.get(GlobalConfig)
    level_map: dict[str, LoggingLevelEnum] = {
        "off": LoggingLevelEnum.Off,
        "error": LoggingLevelEnum.Error,
        "warning": LoggingLevelEnum.Warn,
        "info": LoggingLevelEnum.Info,
        "debug": LoggingLevelEnum.Debug,
        "trace": LoggingLevelEnum.Trace,
    }
    return level_map.get(global_cfg.maa_stdout_level, LoggingLevelEnum.Off)


def resolve_maa_log_file(root_dir: Path | None = None) -> Path:
    base_dir = root_dir or get_runtime_dir()
    global_cfg = config.get(GlobalConfig)
    return resolve_path_from_runtime(global_cfg.maa_log_dir, base_dir)


def resolve_maa_log_dir(root_dir: Path | None = None) -> Path:
    return resolve_maa_log_file(root_dir).parent
