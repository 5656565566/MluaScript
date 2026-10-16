from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from mluascript.control.workspace.models import ScriptRunLocator
from mluascript.maa.lifecycle import bind_controller
from mluascript.maa.lua_exports import build_maa_exports
from mluascript.runtime.engine import LuaEngine

from .models import RunStatus, ScriptRunContext
from .runtime_host import RuntimeHost
from .script_resources import acquire_script_maa_context


def create_script_run_context(
        locator: ScriptRunLocator,
        controller: object | None = None,
        connection_label: str | None = None
    ) -> ScriptRunContext:
    """根据 workspace locator 创建脚本驱动 Maa 的执行上下文"""
    maa_context = acquire_script_maa_context(Path(locator.resource_dir), controller)

    if controller is not None:
        bind_controller(maa_context, controller)
        if connection_label:
            maa_context.mark_connected(connection_label)

    runtime_root = Path(locator.script_dir)
    placeholder_runtime = LuaEngine(
        path=runtime_root,
        host_api=RuntimeHostPlaceholder(),
        lock_project_modules=locator.project.module_search_locked,
        source_overrides=locator.source_overrides,
    )
    context = ScriptRunContext(
        run_id=uuid4().hex,
        runtime=placeholder_runtime,
        maa=maa_context,
        locator=locator,
        status=RunStatus.IDLE,
    )
    runtime = LuaEngine(
        path=runtime_root,
        host_api=RuntimeHost(context),
        lock_project_modules=locator.project.module_search_locked,
        source_overrides=locator.source_overrides,
    )
    runtime.register_namespace("maa", lambda lua: build_maa_exports(lua, context.maa))
    context.runtime = runtime
    maa_context.state.extras["check_stop"] = runtime._check_stop
    return context


class RuntimeHostPlaceholder:
    def print(self, message: str) -> None:
        _ = message

    def write(self, data: str) -> None:
        _ = data

    def log(self, level: str, message: str) -> None:
        _ = (level, message)

    def notify(self, message: str) -> None:
        _ = message

    def check_stop(self) -> None:
        return

    def clear_output(self) -> None:
        return

    def set_output_limit(self, max_lines: int) -> int:
        return int(max_lines)

    def get_output_limit(self) -> int:
        return 300
