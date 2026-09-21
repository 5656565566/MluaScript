from __future__ import annotations

from .base import MaaController, ensure_controller, wait_for
from ..lifecycle.runtime import MaaContext


def click(context: MaaContext, x: int | float, y: int | float) -> bool:
    controller: MaaController = ensure_controller(context)
    wait_for(controller.post_click(int(round(x)), int(round(y))), operation="click")
    return True


def press_key(context: MaaContext, key: int) -> bool:
    controller: MaaController = ensure_controller(context)
    wait_for(controller.post_click_key(key), operation="press key")
    return True


def key_down(context: MaaContext, key: int) -> bool:
    controller: MaaController = ensure_controller(context)
    wait_for(controller.post_key_down(key), operation="key down")
    return True


def key_up(context: MaaContext, key: int) -> bool:
    controller: MaaController = ensure_controller(context)
    wait_for(controller.post_key_up(key), operation="key up")
    return True


def input_text(context: MaaContext, text: str) -> bool:
    controller: MaaController = ensure_controller(context)
    wait_for(controller.post_input_text(text), operation="input text")
    return True
