from __future__ import annotations

from pathlib import Path

from lupa.lua54 import LuaRuntime

from mluascript.runtime.engine import LuaEngine, python_namespace_to_lua


class _HostAPI:
    def __init__(self) -> None:
        self.logs: list[tuple[str, str]] = []
        self.stop_checks = 0

    def log(self, level: str, message: str) -> None:
        self.logs.append((level, message))

    def print(self, message: str) -> None:
        _ = message

    def notify(self, message: str) -> None:
        _ = message

    def check_stop(self) -> None:
        self.stop_checks += 1


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
