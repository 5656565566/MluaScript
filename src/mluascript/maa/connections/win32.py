from __future__ import annotations

from mluascript.shared.logging import logger

import ctypes

from maa.controller import Win32Controller

from ..lifecycle.binding import bind_controller
from ..lifecycle.runtime import MaaContext
from .models import ConnectionInfo, Win32ConnectionParams
from .session import ConnectionSession


def connect_win32(context: MaaContext, params: Win32ConnectionParams) -> ConnectionSession:
    """建立 Win32 连接"""
    logger.info(f"Prepare win32 connection: hwnd={params.hwnd}")
    
    c_hwnd = ctypes.c_void_p(params.hwnd) if params.hwnd else None
    kwargs = {}
    if params.screencap_method is not None:
        kwargs["screencap_method"] = params.screencap_method
    if params.mouse_method is not None:
        kwargs["mouse_method"] = params.mouse_method
    if params.keyboard_method is not None:
        kwargs["keyboard_method"] = params.keyboard_method

    controller = Win32Controller(hWnd=c_hwnd, **kwargs)
    
    job = controller.post_connection()
    job.wait()
    
    if not getattr(job, "succeeded", False):
        logger.error(f"Win32 controller post_connection failed for hwnd={params.hwnd}")
        raise RuntimeError(f"Win32 controller connect failed: hwnd={params.hwnd}")

    screencap_job = controller.post_screencap()
    screencap_job.wait()
    if not getattr(screencap_job, "succeeded", False):
        logger.error(f"Win32 controller screen capture failed for hwnd={params.hwnd}")
        raise RuntimeError(f"Win32 controller connect successful but screencap failed: hwnd={params.hwnd}")

    bind_controller(context, controller)
    info = ConnectionInfo(kind="win32", label=f"WIN32:{params.hwnd}", meta={"hwnd": params.hwnd})
    context.mark_connected(info.label)
    return ConnectionSession(info=info, controller=controller)
