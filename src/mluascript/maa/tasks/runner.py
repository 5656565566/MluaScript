from __future__ import annotations

from .models import TaskRequest, TaskResult
from ..lifecycle.runtime import MaaContext


def run_task(context: MaaContext, request: TaskRequest) -> TaskResult:
    """执行 Maa tasker 任务的最小骨架"""
    if context.tasker is None:
        return TaskResult(succeeded=False, detail=None)
    job = context.tasker.post_task(request.entry, request.override)
    job.wait()
    detail = job.get() if hasattr(job, "get") else None
    return TaskResult(succeeded=bool(getattr(job, "succeeded", False)), detail=detail)
