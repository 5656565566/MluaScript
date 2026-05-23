from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

from lupa.lua54 import LuaRuntime

from .exception import LuaExitException
from .host_api import HostAPI
from .inject_lua import build_lua_runtime_inject
from .llm import build_llm_exports
from .threading import RuntimeThreadManager, build_shared_exports, build_thread_exports
from .threading.shared_value import SharedValue
from .utils.table_lua import lua_2_python
from .utils.virtual_io import VirtualIO


NamespaceBuilder = Callable[[LuaRuntime], Any]


class LuaEngine:
    """Lua 脚本运行时管理器"""

    lupa: LuaRuntime | None = None

    def __init__(self, path: Path, host_api: HostAPI):
        self.virtual_io = VirtualIO()
        self.path = path
        self.host_api = host_api
        self.thread_manager = RuntimeThreadManager()
        self.global_shared_store = SharedValue({})
        self._lua_require_base_dir: Path | None = None
        self._main_script: str = ""
        self._namespace_builders: dict[str, NamespaceBuilder] = {}

    def register_namespace(self, name: str, builder: NamespaceBuilder) -> None:
        """注册额外 Lua 命名空间 构建时延迟注入到对应 runtime"""
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Namespace name must not be empty")
        self._namespace_builders[normalized_name] = builder
        if self.lupa is not None:
            self._register_dynamic_namespaces(self.lupa)

    def stop_handler(self, message: str = "") -> None:
        """提供给 Lua 的主动停止处理器"""
        raise LuaExitException(message or "Execution stopped from lua")

    def lua_print_handler(self, *parts: object) -> None:
        """接收 Lua 侧 print 并转交给宿主输出缓冲区"""
        formatted_parts = [format_lua_value(part) for part in parts]
        message = "\t".join(formatted_parts)
        self.host_api.print(message)

    def lua_log_handler(self, level: str, message: str) -> None:
        """接收 Lua 侧日志并转交给宿主"""
        self.host_api.log(level, message)

    def _create_runtime(self) -> LuaRuntime:
        """创建底层 LuaRuntime 实例"""
        return LuaRuntime(unpack_returned_tuples=True)

    def _register_host_globals(self, lua: LuaRuntime) -> None:
        """向 Lua 全局环境注册宿主协作能力"""
        globals_table = lua.globals()
        globals_table["sleep"] = self.sleep_handler
        globals_table["path"] = self.path.as_posix()
        globals_table["print"] = self.lua_print_handler
        globals_table["log_message"] = self.lua_log_handler
        globals_table["stop"] = self.stop_handler
        globals_table["check_stop"] = self.host_api.check_stop

    def _capture_runtime_globals_snapshot(self, lua: LuaRuntime) -> dict[str, Any]:
        """捕获受限 globals 快照 仅保留可安全继承的全局"""
        snapshot: dict[str, Any] = {}
        globals_table = lua.globals()
        for key in list(globals_table.keys()):
            if not isinstance(key, str):
                continue
            if key.startswith("_"):
                continue
            try:
                value = globals_table[key]
            except Exception:
                continue
            if callable(value):
                continue
            try:
                normalized = lua_2_python(value)
            except Exception:
                continue
            if isinstance(normalized, (type(None), bool, int, float, str, list, dict)):
                snapshot[key] = normalized
        return snapshot

    def _apply_runtime_globals_snapshot(self, lua: LuaRuntime, snapshot: dict[str, Any]) -> None:
        """将受限 globals 快照重新注入到子运行时"""
        globals_table = lua.globals()
        for key, value in snapshot.items():
            globals_table[key] = value

    def _register_builtin_namespaces(self, lua: LuaRuntime) -> None:
        """向 Lua 注入 runtime 内建命名空间"""
        globals_table = lua.globals()
        globals_table["shared"] = python_namespace_to_lua(
            lua,
            build_shared_exports(lua, self.global_shared_store),
        )
        globals_table["thread"] = python_namespace_to_lua(
            lua,
            build_thread_exports(
                lua,
                self.thread_manager,
                build_subruntime=self._build_subruntime,
                capture_subruntime_snapshot=lambda: self._capture_runtime_globals_snapshot(lua),
                build_subruntime_from_snapshot=self._build_subruntime_from_snapshot,
            ),
        )
        globals_table["llm"] = python_namespace_to_lua(
            lua,
            build_llm_exports(lua),
        )

    def _register_dynamic_namespaces(self, lua: LuaRuntime) -> None:
        """向 Lua 注入外部注册的动态命名空间"""
        globals_table = lua.globals()
        for name, builder in self._namespace_builders.items():
            globals_table[name] = python_namespace_to_lua(lua, builder(lua))

    def _register_all_namespaces(self, lua: LuaRuntime) -> None:
        """统一注入所有内建与动态命名空间"""
        self._register_builtin_namespaces(lua)
        self._register_dynamic_namespaces(lua)

    def _configure_lua_package_path(self, lua: LuaRuntime) -> None:
        """配置标准 `require()` / `dofile()` 使用的模块搜索路径"""
        base_dir = (self.path or Path(".")).resolve()
        self._lua_require_base_dir = base_dir
        escaped_base = json.dumps(base_dir.as_posix(), ensure_ascii=False)
        lua.execute(
            f'''
            local __lua_base = {escaped_base}
            if package and type(package.path) == "string" then
                local extra = table.concat({{
                    __lua_base .. "/?.lua",
                    __lua_base .. "/?/init.lua",
                }}, ";")
                if not string.find(package.path, extra, 1, true) then
                    package.path = extra .. ";" .. package.path
                end
            end
            '''
        )

    def _install_stop_hook(self, lua: LuaRuntime, *, instruction_interval: int = 5000) -> None:
        """安装统一 stop hook，保证纯 Lua 计算也能响应宿主停止请求"""
        lua.execute(
            f"""
            debug.sethook(function()
                check_stop()
            end, '', {instruction_interval})
            """
        )

    def inject(self) -> LuaRuntime:
        """构建并注入运行时环境"""
        lua = self._create_runtime()
        self._register_host_globals(lua)
        self._configure_lua_package_path(lua)
        build_lua_runtime_inject(lua)
        self._install_stop_hook(lua)
        self.lupa = lua
        self._register_all_namespaces(lua)
        return self.lupa

    def _build_subruntime(self) -> LuaRuntime:
        """构建线程子运行时 并应用主运行时环境快照"""
        if self.lupa is None:
            raise RuntimeError("Main LuaRuntime not initialized")
        snapshot = self._capture_runtime_globals_snapshot(self.lupa)
        return self._build_subruntime_from_snapshot(snapshot)

    def _build_subruntime_from_snapshot(self, snapshot: dict[str, Any]) -> LuaRuntime:
        """根据预先捕获的主运行时快照构建线程子运行时"""
        subruntime = self._create_runtime()
        self._register_host_globals(subruntime)
        self._configure_lua_package_path(subruntime)
        build_lua_runtime_inject(subruntime)
        self._install_stop_hook(subruntime)
        self._apply_runtime_globals_snapshot(subruntime, snapshot)
        self._register_all_namespaces(subruntime)
        return subruntime

    def execute(self, file_content: str) -> Any:
        """执行一段 Lua 脚本内容"""
        if self.lupa is None:
            self.inject()

        self.host_api.check_stop()
        assert self.lupa is not None
        self._main_script = file_content
        return self.lupa.execute(file_content)

    def sleep_handler(self, seconds: float = 1.0) -> None:
        """休眠处理器，期间持续检查停止标记"""
        if seconds <= 0:
            self.host_api.check_stop()
            return

        end_time = time.time() + seconds
        while True:
            self.host_api.check_stop()
            remaining = end_time - time.time()
            if remaining <= 0:
                break
            time.sleep(min(0.1, remaining))


def python_namespace_to_lua(lua: LuaRuntime, namespace: Any) -> Any:
    """将 Python 命名空间对象映射为 Lua table"""
    table = lua.table()
    if isinstance(namespace, dict):
        names = namespace
    else:
        names = {
            name: getattr(namespace, name)
            for name in dir(namespace)
            if not name.startswith("_")
        }
    for key, value in names.items():
        table[key] = value
    return table


def format_lua_value(value: Any, visited: set[int] | None = None) -> str:
    """将 Lua/Python 值格式化为便于阅读的字符串"""
    if visited is None:
        visited = set()

    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")

    normalized = _normalize_lua_print_value(value, visited)
    if isinstance(normalized, (list, dict)):
        return json.dumps(normalized, ensure_ascii=False, indent=2)
    return str(normalized)



def _normalize_lua_print_value(value: Any, visited: set[int]) -> Any:
    """优先将 Lua table 等复杂值转换为 Python 可读结构"""
    try:
        return lua_2_python(value, visited)
    except Exception:
        return value
