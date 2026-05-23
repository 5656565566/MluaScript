from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from typing import Any, Callable

from lupa.lua54 import LuaRuntime

from .manager import RuntimeThreadManager
from .shared_value import LuaSharedValueView, SharedValue
from .task import RuntimeTask
from ..utils.table_lua import lua_2_python, python_2_lua

 
class LuaTaskHandle:
    """面向 Lua 暴露的任务句柄包装"""

    def __init__(self, task: RuntimeTask) -> None:
        self._task = task

    def id(self) -> str:
        return self._task.id()

    def is_alive(self) -> bool:
        return self._task.is_alive

    def is_done(self) -> bool:
        return self._task.is_done

    def is_cancelled(self) -> bool:
        return self._task.is_cancelled

    def cancel(self) -> bool:
        return self._task.cancel()

    def join(self, timeout: float = 0) -> bool:
        return self._task.join(timeout)

    def result(self) -> Any:
        return self._task.result()

    def error(self) -> str:
        return self._task.error()

    def status(self) -> dict[str, Any]:
        return self._task.status()


@dataclass(slots=True)
class LuaSharedExports:
    """shared 命名空间导出"""

    lupa: LuaRuntime
    global_store: SharedValue

    def value(self, initial: Any = None) -> LuaSharedValueView:
        return LuaSharedValueView(SharedValue(initial), self.lupa)
    
    def get_key(self, key: Any, default: Any = None) -> Any:
        return self.global_store.get_key(key, default, self.lupa)

    def set_key(self, key: Any, value: Any) -> Any:
        return self.global_store.set_key(key, value)
        
    def get(self) -> Any:
        return self.global_store.get(self.lupa)


@dataclass(slots=True)
class LuaThreadExports:
    """thread 命名空间导出"""

    manager: RuntimeThreadManager
    build_subruntime: Callable[[], LuaRuntime]
    capture_subruntime_snapshot: Callable[[], Any] | None
    build_subruntime_from_snapshot: Callable[[Any], LuaRuntime] | None
    lupa: LuaRuntime

    def spawn(self, function_name: str, name: str | None = None, *args) -> LuaTaskHandle:
        if not isinstance(function_name, str) or not function_name.strip():
            raise ValueError("First parameter of thread.spawn must be a string of global function name")
        function_name = function_name.strip()
        globals_table = self.lupa.globals()
        function_ref = globals_table[function_name]
        if function_ref is None:
            raise ValueError(f"Thread target function does not exist: {function_name}")
        if not callable(function_ref):
            raise ValueError(f"Thread target is not callable globally: {function_name}, type={type(function_ref)!r}")
        
        string_dump = globals_table["safe_dump"]
        bytecode = string_dump(function_ref) # type: ignore
        safe_args = [lua_2_python(arg) for arg in args]
        snapshot = self.capture_subruntime_snapshot() if self.capture_subruntime_snapshot is not None else None

        def target(cancel_event: Event) -> Any:
            if self.build_subruntime_from_snapshot is not None:
                subruntime = self.build_subruntime_from_snapshot(snapshot)
            else:
                subruntime = self.build_subruntime()
            globals_table = subruntime.globals()
            globals_table["is_cancelled"] = cancel_event.is_set
            load_func = subruntime.eval("safe_load")
            sub_function_ref = load_func(bytecode) # type: ignore
            if sub_function_ref is None:
                raise ValueError(f"Failed to deserialize target function in sub-thread: {function_name}")
            
            lua_args = [python_2_lua(subruntime, arg) for arg in safe_args]
            result = sub_function_ref(*lua_args)
            return result

        task = self.manager.create_task(target, name=name or function_name)
        self.manager.start_task(task)
        return LuaTaskHandle(task)

    def list(self) -> list[dict[str, Any]]:
        return [task.status() for task in self.manager.list()]

    def get(self, task_id: str) -> LuaTaskHandle | None:
        task = self.manager.get(task_id)
        if task is None:
            return None
        return LuaTaskHandle(task)

    def cancel(self, task_id: str) -> bool:
        return self.manager.cancel(task_id)

    def cleanup(self) -> int:
        return self.manager.cleanup()


def build_shared_exports(lupa: LuaRuntime, global_store: SharedValue) -> LuaSharedExports:
    """构建 shared 命名空间导出"""
    return LuaSharedExports(lupa=lupa, global_store=global_store)


def build_thread_exports(
    lupa: LuaRuntime,
    manager: RuntimeThreadManager,
    *,
    build_subruntime: Callable[[], LuaRuntime] | None = None,
    capture_subruntime_snapshot: Callable[[], Any] | None = None,
    build_subruntime_from_snapshot: Callable[[Any], LuaRuntime] | None = None,
) -> LuaThreadExports:
    """构建 thread 命名空间导出"""
    if build_subruntime is None:
        build_subruntime = lambda: lupa
    return LuaThreadExports(
        manager=manager,
        build_subruntime=build_subruntime,
        capture_subruntime_snapshot=capture_subruntime_snapshot,
        build_subruntime_from_snapshot=build_subruntime_from_snapshot,
        lupa=lupa
    )
