from __future__ import annotations

from .base import MaaController, SupportsShape, ensure_controller, wait_for_result
from ..lifecycle.runtime import MaaContext


def screencap(context: MaaContext) -> SupportsShape | None:
    controller: MaaController = ensure_controller(context)
    waited = wait_for_result(controller.post_screencap())
    if not waited.succeeded:
        return None
    return waited.get()
