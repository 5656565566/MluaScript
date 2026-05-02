from __future__ import annotations

from mluascript.maa.tasks.stop import stop_tasker

from .models import MaaPipelineRunContext, RunStatus, ScriptRunContext


def cancel_script_run(context: ScriptRunContext) -> None:
    """取消 Lua 驱动 Maa 的整次执行"""
    context.status = RunStatus.STOPPING
    context.stopper.request_stop()
    stop_tasker(context.maa)
    context.status = RunStatus.STOPPED


def stop_pipeline_run(context: MaaPipelineRunContext) -> None:
    """停止纯 Maa pipeline 运行"""
    context.status = RunStatus.STOPPING
    stop_tasker(context.maa)
    context.status = RunStatus.STOPPED
