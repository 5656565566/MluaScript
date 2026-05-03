from __future__ import annotations

from .base import MaaController, ensure_controller, wait_for_result
from ..lifecycle.runtime import MaaContext


def shell(context: MaaContext, command: str) -> str | None:
    controller: MaaController = ensure_controller(context)
    if not hasattr(controller, "post_shell"):
        return None
    
    waited = wait_for_result(controller.post_shell(command))
    if not waited.succeeded:
        return None
    
    result = waited.get()
    if isinstance(result, bytes):
        return result.decode('utf-8', errors='replace')
    return str(result)
