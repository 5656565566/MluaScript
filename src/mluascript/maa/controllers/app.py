from __future__ import annotations

from .base import run_controller_operation
from ..lifecycle.runtime import MaaContext


def start_app(context: MaaContext, intent: str) -> bool:
    run_controller_operation(
        context,
        lambda controller: controller.post_start_app(intent),
        operation="start app",
        replay_after_reconnect=True,
    )
    return True


def stop_app(context: MaaContext, intent: str) -> bool:
    run_controller_operation(
        context,
        lambda controller: controller.post_stop_app(intent),
        operation="stop app",
        replay_after_reconnect=True,
    )
    return True
