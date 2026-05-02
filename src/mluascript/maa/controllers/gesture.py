from __future__ import annotations

from .base import MaaController, ensure_controller, wait_for
from ..lifecycle.runtime import MaaContext


def swipe(context: MaaContext, x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> bool:
    controller: MaaController = ensure_controller(context)
    wait_for(controller.post_swipe(x1, y1, x2, y2, duration))
    return True


def touch_down(context: MaaContext, x: int, y: int, contact: int = 0) -> bool:
    controller: MaaController = ensure_controller(context)
    wait_for(controller.post_touch_down(x, y, contact))
    return True


def touch_move(context: MaaContext, x: int, y: int, contact: int = 0) -> bool:
    controller: MaaController = ensure_controller(context)
    wait_for(controller.post_touch_move(x, y, contact))
    return True


def touch_up(context: MaaContext, contact: int = 0) -> bool:
    controller: MaaController = ensure_controller(context)
    wait_for(controller.post_touch_up(contact))
    return True


def scroll(context: MaaContext, dx: int, dy: int) -> bool:
    controller: MaaController = ensure_controller(context)
    wait_for(controller.post_scroll(dx, dy))
    return True
