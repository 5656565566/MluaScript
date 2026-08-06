from __future__ import annotations

import json
import time
from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class RuntimeGlobalsSnapshot:
    """可安全复制到子运行时的全局值与 Lua 函数字节码"""

    values: dict[str, Any]
    functions: dict[str, str]


class LuaEngine:
    """Lua 脚本运行时管理器"""

    lupa: LuaRuntime | None = None

    def __init__(
        self,
        path: Path,
        host_api: HostAPI,
        *,
        lock_project_modules: bool = False,
        source_overrides: dict[str, str] | None = None,
    ):
        self.virtual_io = VirtualIO()
        self.path = path
        self.host_api = host_api
        self.lock_project_modules = bool(lock_project_modules)
        self.source_overrides = {
            str(path).strip().replace("\\", "/"): str(source)
            for path, source in (source_overrides or {}).items()
        }
        self.thread_manager = RuntimeThreadManager()
        self.global_shared_store = SharedValue({})
        self._lua_require_base_dir: Path | None = None
        self._main_script: str = ""
        self._namespace_builders: dict[str, NamespaceBuilder] = {}
        self._builtin_lua_function_bytecodes: dict[str, str] = {}

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
        globals_table["clear_output"] = self.host_api.clear_output
        globals_table["set_output_limit"] = self.host_api.set_output_limit
        globals_table["get_output_limit"] = self.host_api.get_output_limit

    def _capture_runtime_globals_snapshot(self, lua: LuaRuntime) -> RuntimeGlobalsSnapshot:
        """捕获受限 globals 快照及可在子运行时重建的 Lua 全局函数"""
        values: dict[str, Any] = {}
        functions = {
            key: bytecode
            for key, bytecode in self._dump_lua_global_functions(lua).items()
            if self._builtin_lua_function_bytecodes.get(key) != bytecode
        }
        globals_table = lua.globals()
        for key in list(globals_table.keys()):
            if not isinstance(key, str):
                continue
            try:
                value = globals_table[key]
            except Exception:
                continue

            if callable(value):
                continue

            # 保持原有私有值隔离规则；函数不受此前缀限制，因为 Blockly
            # 会将中文函数名编码为以 _E 开头的合法 Lua 标识符。
            if key.startswith("_"):
                continue
            try:
                normalized = lua_2_python(value)
            except Exception:
                continue
            if isinstance(normalized, (type(None), bool, int, float, str, list, dict)):
                values[key] = normalized
        return RuntimeGlobalsSnapshot(values=values, functions=functions)

    def _dump_lua_global_functions(self, lua: LuaRuntime) -> dict[str, str]:
        """序列化当前 Runtime 中可由 string.dump 处理的 Lua 全局函数"""
        functions: dict[str, str] = {}
        globals_table = lua.globals()
        safe_dump = globals_table["safe_dump"]
        for key in list(globals_table.keys()):
            if not isinstance(key, str):
                continue
            try:
                value = globals_table[key]
            except Exception:
                continue
            if not callable(value):
                continue

            # Python callable 和 Lua C 函数无法由 string.dump 序列化，
            # 这里只继承纯 Lua 函数，其他宿主能力会由命名空间重新注册。
            try:
                bytecode = safe_dump(value)
            except Exception:
                continue
            if isinstance(bytecode, str) and bytecode:
                functions[key] = bytecode
        return functions

    def _apply_runtime_globals_snapshot(self, lua: LuaRuntime, snapshot: RuntimeGlobalsSnapshot) -> None:
        """将受限全局值和 Lua 函数重新注入到子运行时"""
        globals_table = lua.globals()
        for key, value in snapshot.values.items():
            globals_table[key] = value

        safe_load = globals_table["safe_load"]
        for key, bytecode in snapshot.functions.items():
            function_ref = safe_load(bytecode)
            if function_ref is None:
                raise ValueError(f"Failed to restore Lua global function in sub-thread: {key}")
            globals_table[key] = function_ref

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
        if self.lock_project_modules:
            self._configure_locked_project_modules(lua, base_dir)
            return
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

    def _read_project_module(self, module_key: object) -> tuple[str | None, str]:
        """读取受限模块空间中的 Lua 源码，不允许回退到宿主搜索路径。"""

        raw_key = str(module_key or "").strip().replace("\\", "/")
        if not raw_key or raw_key.startswith("/") or ":" in raw_key:
            return None, f"\n\tinvalid project module: {raw_key}"
        parts = raw_key.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            return None, f"\n\tinvalid project module: {raw_key}"

        base_dir = (self._lua_require_base_dir or self.path or Path(".")).resolve()
        for relative in (Path(*parts).with_suffix(".lua"), Path(*parts) / "init.lua"):
            virtual_path = f"scripts/{relative.as_posix()}"
            if virtual_path in self.source_overrides:
                return self.source_overrides[virtual_path], virtual_path
            candidate = (base_dir / relative).resolve()
            try:
                candidate.relative_to(base_dir)
            except ValueError:
                continue
            if candidate.is_file() and not candidate.is_symlink():
                try:
                    return candidate.read_text(encoding="utf-8"), virtual_path
                except (OSError, UnicodeError) as exc:
                    return None, f"\n\tfailed to read scripts/{relative.as_posix()}: {exc}"
        return None, f"\n\tno project module 'scripts/{raw_key}.lua' or 'scripts/{raw_key}/init.lua'"

    def _read_project_file(self, virtual_path: object) -> tuple[str | None, str]:
        """为受限 loadfile/dofile 解析 scripts/ 虚拟路径。"""

        raw_path = str(virtual_path or "").strip().replace("\\", "/")
        if not raw_path.startswith("scripts/") or not raw_path.casefold().endswith(".lua"):
            return None, f"只允许读取 scripts/ 内的 Lua 文件: {raw_path}"
        module_key = raw_path[len("scripts/"):-len(".lua")]
        return self._read_project_module(module_key)

    def _configure_locked_project_modules(self, lua: LuaRuntime, base_dir: Path) -> None:
        """安装只暴露 preload 与项目虚拟模块的 Lua package 环境。"""

        self._lua_require_base_dir = base_dir
        globals_table = lua.globals()
        globals_table["__mlua_read_project_module"] = self._read_project_module
        globals_table["__mlua_read_project_file"] = self._read_project_file
        lua.execute(
            r'''
            local __real_package = package
            local function __project_searcher(name)
                local source, virtual_path = __mlua_read_project_module(name)
                if not source then return virtual_path end
                local chunk, err = load(source, "@" .. virtual_path, "t", _ENV)
                if not chunk then return "\n\t" .. err end
                return chunk, virtual_path
            end

            __real_package.path = "scripts/?.lua;scripts/?/init.lua"
            __real_package.cpath = ""
            __real_package.searchers = { __real_package.searchers[1], __project_searcher }

            local __searchers_view = setmetatable({}, {
                __index = __real_package.searchers,
                __newindex = function() error("project package.searchers is read-only", 2) end,
                __len = function() return #__real_package.searchers end,
            })
            local __package_view = {
                loaded = __real_package.loaded,
                preload = __real_package.preload,
                path = __real_package.path,
                cpath = __real_package.cpath,
                searchers = __searchers_view,
                searchpath = function(name)
                    local source, virtual_path = __mlua_read_project_module(name)
                    if source then return virtual_path end
                    return nil, virtual_path
                end,
            }
            package = setmetatable({}, {
                __index = __package_view,
                __newindex = function() error("project package configuration is read-only", 2) end,
                __metatable = "locked project package",
            })

            loadfile = function(filename, mode, env)
                local source, virtual_path = __mlua_read_project_file(filename)
                if not source then return nil, virtual_path end
                return load(source, "@" .. virtual_path, mode or "t", env or _ENV)
            end
            dofile = function(filename)
                local chunk, err = loadfile(filename, "t", _ENV)
                if not chunk then error(err, 2) end
                return chunk()
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
        # 记录运行时自带函数，后续快照仅复制脚本新增或覆盖的函数。
        # 这些内置函数可能持有局部 upvalue，必须由注入脚本原样重建。
        self._builtin_lua_function_bytecodes = self._dump_lua_global_functions(lua)
        self.lupa = lua
        self._register_all_namespaces(lua)
        return self.lupa

    def _build_subruntime(self) -> LuaRuntime:
        """构建线程子运行时 并应用主运行时环境快照"""
        if self.lupa is None:
            raise RuntimeError("Main LuaRuntime not initialized")
        snapshot = self._capture_runtime_globals_snapshot(self.lupa)
        return self._build_subruntime_from_snapshot(snapshot)

    def _build_subruntime_from_snapshot(self, snapshot: RuntimeGlobalsSnapshot) -> LuaRuntime:
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
