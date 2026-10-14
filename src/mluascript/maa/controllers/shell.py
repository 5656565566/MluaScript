from __future__ import annotations

from .base import locked_controller, wait_for_result
from ..compat import configure_shell_api
from ..lifecycle.runtime import MaaContext


def shell(context: MaaContext, command: str) -> str | None:
    with locked_controller(context) as controller:
        if not hasattr(controller, "post_shell"):
            return None

        configure_shell_api()
        waited = wait_for_result(controller.post_shell(command))
        if not waited.succeeded:
            return None

        result = waited.get()
    if isinstance(result, bytes):
        return result.decode('utf-8', errors='replace')
    return str(result)
