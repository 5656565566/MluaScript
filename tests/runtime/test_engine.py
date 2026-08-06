from __future__ import annotations

from pathlib import Path

import pytest
from lupa.lua54 import LuaRuntime

from mluascript.runtime.engine import LuaEngine, python_namespace_to_lua
from mluascript.runtime.output_buffer import TaskOutputBuffer


class _HostAPI:
    def __init__(self) -> None:
        self.logs: list[tuple[str, str]] = []
        self.stop_checks = 0
        self.output = TaskOutputBuffer()

    def log(self, level: str, message: str) -> None:
        self.logs.append((level, message))

    def print(self, message: str) -> None:
        self.output.append(message)

    def notify(self, message: str) -> None:
        _ = message

    def check_stop(self) -> None:
        self.stop_checks += 1

    def clear_output(self) -> None:
        self.output.clear()

    def set_output_limit(self, max_lines: int) -> int:
        return self.output.set_max_lines(max_lines)

    def get_output_limit(self) -> int:
        return self.output.max_lines


def test_python_namespace_to_lua_builds_table() -> None:
    lua = LuaRuntime(unpack_returned_tuples=True)
    table = python_namespace_to_lua(lua, {"name": "mlua", "value": 1})

    assert table["name"] == "mlua"
    assert table["value"] == 1


def test_engine_creates_runtime() -> None:
    engine = LuaEngine(Path("."), _HostAPI())

    runtime = engine._create_runtime()

    assert runtime is not None


def test_engine_registers_host_globals() -> None:
    engine = LuaEngine(Path("."), _HostAPI())
    lua = LuaRuntime(unpack_returned_tuples=True)

    engine._register_host_globals(lua)
    globals_table = lua.globals()

    assert callable(globals_table["sleep"])
    assert callable(globals_table["log_message"])
    assert callable(globals_table["stop"])
    assert callable(globals_table["check_stop"])
    assert callable(globals_table["clear_output"])
    assert callable(globals_table["set_output_limit"])
    assert callable(globals_table["get_output_limit"])
    assert globals_table["path"] == Path(".").as_posix()


def test_engine_registers_builtin_namespaces() -> None:
    engine = LuaEngine(Path("."), _HostAPI())
    lua = LuaRuntime(unpack_returned_tuples=True)

    engine._register_builtin_namespaces(lua)
    globals_table = lua.globals()

    assert globals_table["shared"] is not None
    assert globals_table["thread"] is not None
    assert globals_table["llm"] is not None


def test_engine_register_namespace_injects_dynamic_namespace() -> None:
    engine = LuaEngine(Path("."), _HostAPI())
    lua = LuaRuntime(unpack_returned_tuples=True)

    engine.register_namespace("maa", lambda _: {"ping": lambda: "pong"})
    engine._register_dynamic_namespaces(lua)
    globals_table = lua.globals()

    assert globals_table["maa"]["ping"]() == "pong"


def test_engine_register_namespace_updates_existing_runtime() -> None:
    engine = LuaEngine(Path("."), _HostAPI())
    lua = engine.inject()

    engine.register_namespace("maa", lambda _: {"device": "ok"})

    assert lua.globals()["maa"]["device"] == "ok"


def test_engine_log_handler_forwards_to_host() -> None:
    host = _HostAPI()
    engine = LuaEngine(Path("."), host)

    engine.lua_log_handler("INFO", "hello")

    assert host.logs == [("INFO", "hello")]


def test_engine_sleep_handler_checks_stop_for_non_positive_sleep() -> None:
    host = _HostAPI()
    engine = LuaEngine(Path("."), host)

    engine.sleep_handler(0)

    assert host.stop_checks == 1


def test_engine_execute_runs_script_content() -> None:
    host = _HostAPI()
    engine = LuaEngine(Path("."), host)

    result = engine.execute("return 123")

    assert result == 123
    assert host.stop_checks >= 1
    assert engine.lupa is not None


def test_locked_project_modules_prefer_in_memory_source_override(tmp_path: Path) -> None:
    scripts = tmp_path / "scripts"
    module = scripts / "lib" / "math.lua"
    module.parent.mkdir(parents=True)
    module.write_text("return { value = 'disk' }\n", encoding="utf-8")
    engine = LuaEngine(
        scripts,
        _HostAPI(),
        lock_project_modules=True,
        source_overrides={"scripts/lib/math.lua": "return { value = 'memory' }\n"},
    )

    result = engine.execute("return require('lib/math').value")

    assert result == "memory"



def test_engine_lua_print_handler_formats_lua_table_readably() -> None:
    class _PrintHostAPI(_HostAPI):
        def __init__(self) -> None:
            super().__init__()
            self.printed: list[str] = []

        def print(self, message: str) -> None:
            self.printed.append(message)

    host = _PrintHostAPI()
    engine = LuaEngine(Path("."), host)
    lua = LuaRuntime(unpack_returned_tuples=True)
    table = lua.eval('{ name = "mlua", items = { 1, 2 } }')

    engine.lua_print_handler(table)

    assert len(host.printed) == 1
    assert '"name": "mlua"' in host.printed[0]
    assert '"items": [' in host.printed[0]
    assert '<Lua table at' not in host.printed[0]


def test_task_output_buffer_trims_lines_by_limit() -> None:
    buffer = TaskOutputBuffer(max_lines=3)

    buffer.append("1")
    buffer.append("2")
    buffer.append("3")
    buffer.append("4")

    assert list(buffer) == ["2", "3", "4"]
    assert buffer.total_lines == 4


def test_engine_global_output_helpers_control_output_buffer() -> None:
    host = _HostAPI()
    engine = LuaEngine(Path("."), host)

    result = engine.execute(
        '''
        print("keep-1")
        print("keep-2")
        clear_output()
        set_output_limit(2)
        print("after-1")
        print("after-2")
        print("after-3")
        return get_output_limit()
        '''
    )

    assert result == 2
    assert list(host.output) == ["after-2", "after-3"]
    assert host.output.max_lines == 2


def test_locked_project_modules_use_virtual_scripts_paths(tmp_path: Path) -> None:
    scripts = tmp_path / "scripts"
    module = scripts / "lib" / "math.lua"
    module.parent.mkdir(parents=True)
    module.write_text("return { add = function(a, b) return a + b end }\n", encoding="utf-8")
    engine = LuaEngine(scripts, _HostAPI(), lock_project_modules=True)

    result = engine.execute(
        '''
        local math = require("lib/math")
        local found = package.searchpath("lib/math", package.path)
        return math.add(2, 3), package.path, package.cpath, found
        '''
    )

    assert result == (5, "scripts/?.lua;scripts/?/init.lua", "", "scripts/lib/math.lua")


def test_locked_project_modules_reject_host_fallback_and_configuration_changes(tmp_path: Path) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    engine = LuaEngine(scripts, _HostAPI(), lock_project_modules=True)

    with pytest.raises(Exception, match="read-only"):
        engine.execute('package.path = "../?.lua"')
    with pytest.raises(Exception, match="read-only"):
        engine.execute('package.searchers[1] = function() end')
    with pytest.raises(Exception, match="no project module"):
        engine.execute('return require("outside")')
