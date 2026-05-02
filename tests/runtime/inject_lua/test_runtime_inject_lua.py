from __future__ import annotations

from pathlib import Path

from mluascript.runtime.inject_lua import CORE_MODULES, build_lua_runtime_inject, load_lua_script, load_lua_scripts


class _FakeLuaRuntime:
    def __init__(self) -> None:
        self.executed_scripts: list[str] = []

    def execute(self, script: str) -> None:
        self.executed_scripts.append(script)


def test_load_lua_script_reads_existing_module() -> None:
    content = load_lua_script("utils")

    assert isinstance(content, str)
    assert len(content) > 0


def test_load_lua_script_raises_for_missing_module() -> None:
    missing_name = "module_that_does_not_exist"

    try:
        load_lua_script(missing_name)
    except FileNotFoundError as exc:
        assert missing_name in str(exc)
    else:
        raise AssertionError("expected FileNotFoundError")


def test_load_lua_scripts_joins_multiple_modules() -> None:
    content = load_lua_scripts("utils", "json")

    assert "\n\n" in content
    assert len(content) >= len(load_lua_script("utils"))


def test_build_lua_runtime_inject_executes_core_modules() -> None:
    fake = _FakeLuaRuntime()

    result = build_lua_runtime_inject(fake) # type: ignore

    assert result is fake
    assert len(fake.executed_scripts) == 1
    for module_name in CORE_MODULES:
        assert module_name != ""
