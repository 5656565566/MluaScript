from __future__ import annotations

from mluascript.control.workspace.models import PipelineRunLocator, ScriptRunLocator

from .models import MaaPipelineRunContext, ScriptRunContext
from .pipeline_run import create_pipeline_run_context
from .script_run import create_script_run_context
from .stop import cancel_script_run, stop_pipeline_run


class IntegrationFacade:
    """运行装配与停止传播入口"""

    def create_script_run(
        self,
        locator: ScriptRunLocator,
        controller: object | None = None,
        connection_label: str | None = None,
    ) -> ScriptRunContext:
        return create_script_run_context(
            locator,
            controller=controller,
            connection_label=connection_label,
        )

    def create_pipeline_run(
        self,
        locator: PipelineRunLocator,
        controller: object | None = None,
        connection_label: str | None = None,
    ) -> MaaPipelineRunContext:
        return create_pipeline_run_context(
            locator,
            controller=controller,
            connection_label=connection_label,
        )

    def cancel_script_run(self, context: ScriptRunContext) -> None:
        cancel_script_run(context)

    def stop_pipeline_run(self, context: MaaPipelineRunContext) -> None:
        stop_pipeline_run(context)
