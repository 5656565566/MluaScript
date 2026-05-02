from __future__ import annotations

from .base import MaaController, ensure_controller, wait_for
from ..lifecycle.runtime import MaaContext


def start_app(context: MaaContext, intent: str) -> bool:
    controller: MaaController = ensure_controller(context)
    wait_for(controller.post_start_app(intent))
    return True


def stop_app(context: MaaContext, intent: str) -> bool:
    controller: MaaController = ensure_controller(context)
    wait_for(controller.post_stop_app(intent))
    return True
