from __future__ import annotations

from pathlib import Path

from maa.define import LoggingLevelEnum
from mluascript.shared.config import GlobalConfig, config

from ..types import MaaPaths


def _normalize_adb_path(raw: str) -> Path:
    path = Path(raw)
    if path.name.lower() not in {"adb", "adb.exe"}:
        return path / "adb.exe"
    return path


def resolve_maa_paths(root_dir: Path | None = None) -> MaaPaths:
    """根据当前配置解析 Maa 运行路径"""
    base_dir = root_dir or Path.cwd()
    global_cfg = config.get(GlobalConfig)

    library_dir = Path(global_cfg.maa_library_dir) if global_cfg.maa_library_dir else base_dir / "maafw"
    resource_dir = Path(global_cfg.maa_resource_dir) if global_cfg.maa_resource_dir else base_dir / "resource"
    model_dir = Path(global_cfg.maa_model_dir) if global_cfg.maa_model_dir else None
    adb_path = _normalize_adb_path(global_cfg.maa_adb_dir) if global_cfg.maa_adb_dir else None

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
