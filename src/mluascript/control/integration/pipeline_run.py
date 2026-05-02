from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from mluascript.control.workspace.models import PipelineRunLocator
from mluascript.maa.lifecycle import create_maa_context, bind_controller, initialize_maa_runtime
from mluascript.maa.types import MaaPaths

from .models import MaaPipelineRunContext, RunStatus


def create_pipeline_run_context(
    locator: PipelineRunLocator,
    controller: object | None = None,
    connection_label: str | None = None,
) -> MaaPipelineRunContext:
    """根据 workspace locator 创建纯 Maa pipeline 运行上下文"""
    maa_context = create_maa_context()
    maa_context.paths = MaaPaths(
        library_dir=maa_context.paths.library_dir,
        resource_dir=Path(locator.resource_dir),
        model_dir=maa_context.paths.model_dir,
        adb_path=maa_context.paths.adb_path,
    )

    initialize_maa_runtime(maa_context)

    if controller is not None:
        bind_controller(maa_context, controller)
        if connection_label:
            maa_context.mark_connected(connection_label)

    return MaaPipelineRunContext(
        run_id=uuid4().hex,
        maa=maa_context,
        locator=locator,
        status=RunStatus.IDLE,
    )
