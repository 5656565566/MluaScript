from __future__ import annotations

from typing import Dict, Optional

from mluascript.control.integration.facade import IntegrationFacade

from .pipeline import PipelineExecutionUseCase
from .script import ScriptExecutionUseCase


class ExecutionManager:
    """运行调度中心 聚合 Script 与 Pipeline 的高层用例"""

    def __init__(self) -> None:
        self.integration_facade = IntegrationFacade()
        self.script_use_case = ScriptExecutionUseCase(self.integration_facade)
        self.pipeline_use_case = PipelineExecutionUseCase(self.integration_facade)

    def start_script(
        self,
        script_path: str,
        code: str,
        target: str,
        *,
        title: str | None = None,
        source_overrides: Dict[str, str] | None = None,
        summary: Dict[str, object] | None = None,
        cleanup_dir: str | None = None,
    ) -> str:
        return self.script_use_case.start_script(
            script_path,
            code,
            target,
            title=title,
            source_overrides=source_overrides,
            summary=summary,
            cleanup_dir=cleanup_dir,
        )

    def stop_script(self, task_id: str) -> None:
        self.script_use_case.stop_script(task_id)

    def start_pipeline(
        self,
        entry: str,
        override: Optional[Dict[str, object]],
        target: str,
        project_path: str,
        *,
        title: str | None = None,
        cleanup_dir: str | None = None,
    ) -> str:
        return self.pipeline_use_case.start_pipeline(
            entry,
            override,
            target,
            project_path,
            title=title,
            cleanup_dir=cleanup_dir,
        )

    def stop_pipeline(self, task_id: str) -> None:
        self.pipeline_use_case.stop_pipeline(task_id)


_global_execution_manager = ExecutionManager()


def get_execution_manager() -> ExecutionManager:
    return _global_execution_manager
