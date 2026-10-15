from __future__ import annotations

from mluascript.maa.tasks.stop import stop_tasker

from .models import MaaPipelineRunContext, RunStatus, ScriptRunContext


def cancel_script_run(context: ScriptRunContext) -> None:
    """取消 Lua 驱动 Maa 的整次执行"""
    with context.lifecycle_lock:
        if context.stopper.is_stop_requested:
            return
        context.status = RunStatus.STOPPING
        context.stopper.request_stop()
        try:
            if context.maa.tasker is not None:
                context.maa.state.extras["stop_job"] = context.maa.tasker.post_stop()
        finally:
            context.maa.mark_connected(None)


def stop_pipeline_run(context: MaaPipelineRunContext) -> None:
    """停止纯 Maa pipeline 运行"""
    context.status = RunStatus.STOPPING
    stop_tasker(context.maa)
    context.status = RunStatus.STOPPED
