from __future__ import annotations

from .base import SupportsShape, locked_controller, wait_for_result
from ..lifecycle.runtime import MaaContext


def screencap(context: MaaContext) -> SupportsShape | None:
    with locked_controller(context) as controller:
        waited = wait_for_result(controller.post_screencap())
        if not waited.succeeded:
            return None
        return waited.get()
