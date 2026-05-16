from __future__ import annotations

import platform
import shutil
from pathlib import Path

from maa.define import LoggingLevelEnum
from mluascript.shared.config import GlobalConfig, config
from mluascript.shared.config.manager import get_runtime_dir, resolve_path_from_runtime

from ..types import MaaPaths


def _normalize_adb_path(raw: str) -> Path:
    path = Path(raw)
    if path.name.lower() in {"adb", "adb.exe"}:
        return path

    adb_name = "adb.exe" if platform.system().lower() == "windows" else "adb"
    return path / adb_name


def resolve_maa_paths(root_dir: Path | None = None) -> MaaPaths:
    """根据当前配置解析 Maa 运行路径"""
    base_dir = root_dir or get_runtime_dir()
    global_cfg = config.get(GlobalConfig)

    library_dir = Path(global_cfg.maa_library_dir) if global_cfg.maa_library_dir else base_dir / "maafw"
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
        model_dir=model_dir,
        adb_path=adb_path,
    )


def configure_toolkit_options(paths: MaaPaths) -> dict[str, str]:
    """生成 Maa Toolkit 初始化参数"""
    options: dict[str, str] = {}
    if paths.adb_path is not None:
        options["adb_path"] = str(paths.adb_path)
    return options


def resolve_tasker_stdout_level() -> LoggingLevelEnum:
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


def resolve_maa_log_dir(root_dir: Path | None = None) -> Path:
    base_dir = root_dir or get_runtime_dir()
    global_cfg = config.get(GlobalConfig)
    return resolve_path_from_runtime(global_cfg.maa_log_dir, base_dir)
