from __future__ import annotations

from typing import Any

from maa.toolkit import Toolkit

from mluascript.shared.logging import logger


def _is_valid_mumu_config(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    if not bool(payload.get("enable")):
        return False
    path = str(payload.get("path") or "").strip()
    lib = str(payload.get("lib") or "").strip()
    app_package = str(payload.get("app_package") or "").strip()
    index = payload.get("index")
    app_cloned_index = payload.get("app_cloned_index")
    return bool(path and lib and app_package and isinstance(index, int) and isinstance(app_cloned_index, int))



def find_adb_devices() -> list[dict[str, Any]]:
    """发现可用 ADB 设备"""
    devices = Toolkit.find_adb_devices()
    result = []
    for d in devices:
        item = {
            "name": d.name,
            "adb_path": str(d.adb_path),
            "address": d.address,
            "screencap_methods": d.screencap_methods,
            "input_methods": d.input_methods,
            "config": d.config,
        }
        mumu_config = ((d.config or {}).get("extras") or {}).get("mumu")
        if isinstance(mumu_config, dict) and _is_valid_mumu_config(mumu_config):
            item["mumu"] = mumu_config.copy()
            item["kind"] = "emulator"
            item["emulator_type"] = "mumu"
        result.append(item)
    logger.info(f"Found {len(result)} ADB devices")
    return result



def find_desktop_windows() -> list[dict[str, Any]]:
    """发现可用桌面窗口"""
    windows = Toolkit.find_desktop_windows()
    result = []
    for w in windows:
        result.append({
            "hwnd": int(w.hwnd) if w.hwnd else 0,
            "class_name": w.class_name,
            "window_name": w.window_name,
        })
    logger.info(f"Found {len(result)} desktop windows")
    return result
