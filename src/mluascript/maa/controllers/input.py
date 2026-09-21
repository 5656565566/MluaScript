from __future__ import annotations

from .base import run_controller_operation
from ..lifecycle.runtime import MaaContext


def click(context: MaaContext, x: int | float, y: int | float) -> bool:
    normalized_x = int(round(x))
    normalized_y = int(round(y))
    run_controller_operation(
        context,
        lambda controller: controller.post_click(normalized_x, normalized_y),
        operation="click",
        replay_after_reconnect=True,
    )
    return True


def press_key(context: MaaContext, key: int) -> bool:
    run_controller_operation(
        context,
        lambda controller: controller.post_click_key(key),
        operation="press key",
        replay_after_reconnect=True,
    )
    return True


def key_down(context: MaaContext, key: int) -> bool:
    run_controller_operation(
        context,
        lambda controller: controller.post_key_down(key),
        operation="key down",
        replay_after_reconnect=True,
    )
    return True


def key_up(context: MaaContext, key: int) -> bool:
    run_controller_operation(
        context,
        lambda controller: controller.post_key_up(key),
        operation="key up",
        replay_after_reconnect=True,
    )
    return True


def input_text(context: MaaContext, text: str) -> bool:
    run_controller_operation(
        context,
        lambda controller: controller.post_input_text(text),
        operation="input text",
        replay_after_reconnect=True,
    )
    return True
