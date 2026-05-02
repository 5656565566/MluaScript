from __future__ import annotations

from mluascript.shared.logging import logger

from ..extensions.browser.controller import BrowserController
from ..lifecycle.binding import bind_controller
from ..lifecycle.runtime import MaaContext
from .models import BrowserConnectionParams, ConnectionInfo
from .session import ConnectionSession


def connect_browser(context: MaaContext, params: BrowserConnectionParams) -> ConnectionSession:
    """建立 Browser 连接，走 Maa 官方第三方控制器机制接入"""
    logger.info(f"Prepare browser connection: {params.url}")

    controller = BrowserController(
        params.url,
        browser_type=params.browser_type,
        executable_path=params.executable_path,
        launch_args=params.launch_args,
        profile_dir=params.profile_dir,
        name=params.name,
    )

    job = controller.post_connection()
    job.wait()

    if not getattr(job, "succeeded", False):
        logger.error(f"Browser controller post_connection failed for {params.url}")
        raise RuntimeError(f"Browser controller connect failed: {params.url}")

    screencap_job = controller.post_screencap()
    screencap_job.wait()
    if not getattr(screencap_job, "succeeded", False):
        logger.error(f"Browser controller screen capture failed for {params.url}")
        raise RuntimeError(f"Browser controller connect successful but screencap failed: {params.url}")

    bind_controller(context, controller)
    label = params.name or params.url
    info = ConnectionInfo(
        kind="browser",
        label=f"BROWSER:{label}",
        meta={
            "url": params.url,
            "browser_type": params.browser_type,
            "executable_path": params.executable_path,
            "name": params.name,
        },
    )
    context.mark_connected(info.label)
    return ConnectionSession(info=info, controller=controller)
