from __future__ import annotations

import ctypes
import os
import platform

from maa.controller import MacOSController, Win32Controller, WlRootsController

from mluascript.shared.logging import logger

from ..lifecycle.binding import bind_controller
from ..lifecycle.runtime import MaaContext
from .models import ConnectionInfo, DesktopWindowConnectionParams
from .session import ConnectionSession


def current_desktop_backend() -> str:
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    if system == "darwin":
        return "macos"
    if system == "linux":
        return _detect_linux_desktop_backend()
    return "unknown"


def current_desktop_label() -> str:
    backend = current_desktop_backend()
    if backend == "windows":
        return " Windows 本地窗口"
    if backend == "macos":
        return " macOS 本地窗口"
    if backend in {"wlroots", "x11"}:
        return " Linux 本地窗口"
    return " 本地窗口"


def connect_desktop_window(context: MaaContext, params: DesktopWindowConnectionParams) -> ConnectionSession:
    backend = (params.platform or current_desktop_backend()).lower()
    logger.info(f"Prepare desktop connection: backend={backend}, handle={params.handle}")

    if backend == "windows":
        return _connect_windows(context, params)
    if backend == "macos":
        return _connect_macos(context, params)
    if backend == "wlroots":
        return _connect_wlroots(context, params)
    if backend == "x11":
        raise RuntimeError("当前 Linux 会话为 X11 但当前 MAA 后端仅支持 wlroots/Wayland 本地窗口控制")
    raise RuntimeError(f"当前平台暂不支持本地窗口控制: {platform.system()}")


def _connect_windows(context: MaaContext, params: DesktopWindowConnectionParams) -> ConnectionSession:
    if not params.handle:
        raise RuntimeError("Windows 本地窗口连接缺少有效句柄")

    kwargs: dict[str, int] = {}
    if params.screencap_method is not None:
        kwargs["screencap_method"] = params.screencap_method
    if params.mouse_method is not None:
        kwargs["mouse_method"] = params.mouse_method
    if params.keyboard_method is not None:
        kwargs["keyboard_method"] = params.keyboard_method

    controller = Win32Controller(hWnd=ctypes.c_void_p(params.handle), **kwargs)
    _verify_controller_ready(controller, backend="windows", target=str(params.handle))
    bind_controller(context, controller)
    info = ConnectionInfo(kind="desktop", label=f"DESKTOP:windows:{params.handle}", meta={"platform": "windows", "handle": params.handle})
    context.mark_connected(info.label)
    return ConnectionSession(info=info, controller=controller)


def _connect_macos(context: MaaContext, params: DesktopWindowConnectionParams) -> ConnectionSession:
    if not params.handle:
        raise RuntimeError("macOS 本地窗口连接缺少有效窗口 ID")

    kwargs: dict[str, int] = {}
    if params.screencap_method is not None:
        kwargs["screencap_method"] = params.screencap_method
    if params.input_method is not None:
        kwargs["input_method"] = params.input_method

    controller = MacOSController(window_id=int(params.handle), **kwargs)
    _verify_controller_ready(controller, backend="macos", target=str(params.handle))
    bind_controller(context, controller)
    info = ConnectionInfo(kind="desktop", label=f"DESKTOP:macos:{params.handle}", meta={"platform": "macos", "handle": params.handle})
    context.mark_connected(info.label)
    return ConnectionSession(info=info, controller=controller)


def _connect_wlroots(context: MaaContext, params: DesktopWindowConnectionParams) -> ConnectionSession:
    socket_path = (params.socket_path or _resolve_wlroots_socket_path()).strip()
    if not socket_path:
        raise RuntimeError("Linux 本地窗口控制需要 Wayland/wlroots socket 请设置 WAYLAND_DISPLAY 和 XDG_RUNTIME_DIR")

    controller = WlRootsController(wlr_socket_path=socket_path)
    _verify_controller_ready(controller, backend="wlroots", target=socket_path)
    bind_controller(context, controller)
    info = ConnectionInfo(
        kind="desktop",
        label=f"DESKTOP:wlroots:{socket_path}",
        meta={"platform": "wlroots", "socket_path": socket_path, "handle": params.handle},
    )
    context.mark_connected(info.label)
    return ConnectionSession(info=info, controller=controller)


def _resolve_wlroots_socket_path() -> str:
    wayland_display = str(os.environ.get("WAYLAND_DISPLAY") or "").strip()
    xdg_runtime_dir = str(os.environ.get("XDG_RUNTIME_DIR") or "").strip()
    if not wayland_display:
        return ""
    if os.path.isabs(wayland_display):
        return wayland_display
    if not xdg_runtime_dir:
        return ""
    return os.path.join(xdg_runtime_dir, wayland_display)


def _detect_linux_desktop_backend() -> str:
    session_type = str(os.environ.get("XDG_SESSION_TYPE") or "").strip().lower()
    if session_type == "x11":
        return "x11"
    if session_type == "wayland":
        return "wlroots"

    if str(os.environ.get("WAYLAND_DISPLAY") or "").strip():
        return "wlroots"
    if str(os.environ.get("DISPLAY") or "").strip():
        return "x11"
    return "wlroots"


def _verify_controller_ready(controller, *, backend: str, target: str) -> None:
    job = controller.post_connection()
    job.wait()
    if not getattr(job, "succeeded", False):
        logger.error(f"{backend} controller post_connection failed for target={target}")
        raise RuntimeError(f"{backend} controller connect failed: {target}")

    screencap_job = controller.post_screencap()
    screencap_job.wait()
    if not getattr(screencap_job, "succeeded", False):
        logger.error(f"{backend} controller screen capture failed for target={target}")
        raise RuntimeError(f"{backend} controller connect successful but screencap failed: {target}")
