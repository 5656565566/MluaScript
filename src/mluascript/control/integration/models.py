from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from mluascript.control.workspace.models import PipelineRunLocator, ScriptRunLocator
from mluascript.maa.lifecycle.runtime import MaaContext
from mluascript.runtime.engine import LuaEngine
from mluascript.runtime.stopper import Stopper
from mluascript.runtime.threading.task import RuntimeTask


class RunStatus(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FINISHED = "finished"
    FAILED = "failed"


@dataclass
class ScriptRunContext:
    """Lua 驱动 Maa 的整次执行上下文"""

    run_id: str
    runtime: LuaEngine
    maa: MaaContext
    locator: ScriptRunLocator
    stopper: Stopper = field(default_factory=Stopper)
    status: RunStatus = RunStatus.IDLE
    host_task: RuntimeTask | None = None
    print_buffer: list[str] = field(default_factory=list)
    log_buffer: list[dict[str, str]] = field(default_factory=list)


@dataclass
class MaaPipelineRunContext:
    """纯 Maa pipeline 运行上下文"""

    run_id: str
    maa: MaaContext
    locator: PipelineRunLocator
    status: RunStatus = RunStatus.IDLE
    host_task: RuntimeTask | None = None
