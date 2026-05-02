from __future__ import annotations

from maa.library import Library

from mluascript.shared.logging import logger

from .runtime import MaaContext


def bind_controller(context: MaaContext, controller: object) -> None:
    """绑定 controller 到当前 Maa 上下文"""
    context.controller = controller

    # 使用底层 API 绑定 避免直接调用 Tasker.bind 导致类型不匹配
    controller_handle = getattr(controller, "_handle", None)
    if context.tasker is not None and controller_handle is not None:
        try:
            Library.framework().MaaTaskerBindController(
                context.tasker._handle, controller_handle
            )
        except Exception as exc:
            logger.error(f"Maa tasker 绑定 controller 失败: {exc}")

    label = getattr(controller, "uuid", None)
    context.mark_connected(str(label) if label else None)
    logger.debug("Maa controller bound to context")


def unbind_controller(context: MaaContext) -> None:
    """解除当前 Maa 上下文中的 controller 绑定"""
    context.controller = None
    context.mark_connected(None)
    logger.debug("Maa controller unbound from context")
