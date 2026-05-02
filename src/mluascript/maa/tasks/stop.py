from __future__ import annotations

from ..lifecycle.runtime import MaaContext


def post_stop(context: MaaContext) -> None:
    if context.tasker is None:
        return
    stop_job = context.tasker.post_stop()
    wait = getattr(stop_job, "wait", None)
    if callable(wait):
        wait()


def stop_tasker(context: MaaContext) -> None:
    post_stop(context)
    context.mark_connected(None)
