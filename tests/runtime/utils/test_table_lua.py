from __future__ import annotations

from lupa.lua54 import LuaRuntime

from mluascript.runtime.utils.table_lua import format_lua_value, lua_2_python, python_2_lua


def test_python_2_lua_converts_dict_and_list() -> None:
    lua = LuaRuntime(unpack_returned_tuples=True)

    table = python_2_lua(lua, {"items": [1, 2, 3], "name": "mlua"})

    assert table["name"] == "mlua"
    assert table["items"][1] == 1
    assert table["items"][3] == 3


def test_lua_2_python_converts_array_like_table() -> None:
    lua = LuaRuntime(unpack_returned_tuples=True)
    table = lua.table()
    table[1] = "a"
    table[2] = "b"

    result = lua_2_python(table)

    assert result == ["a", "b"]


def test_lua_2_python_converts_dict_like_table() -> None:
    lua = LuaRuntime(unpack_returned_tuples=True)
    table = lua.table()
    table["name"] = "mlua"
    table["version"] = 1

    result = lua_2_python(table)

    assert result == {"name": "mlua", "version": 1}


def test_format_lua_value_handles_python_values() -> None:
    assert format_lua_value(None) == "nil"
    assert format_lua_value(True) == "true"
    assert format_lua_value(12) == "12"
    assert format_lua_value("hello") == "hello"


def test_format_lua_value_formats_table_as_json() -> None:
    lua = LuaRuntime(unpack_returned_tuples=True)
    table = lua.table()
    table["name"] = "mlua"
    table["items"] = python_2_lua(lua, [1, 2])

    formatted = format_lua_value(table)

    assert '"name": "mlua"' in formatted
    assert '"items": [' in formatted



def test_lua_2_python_converts_lupa_table_proxy() -> None:
    lua = LuaRuntime(unpack_returned_tuples=True)
    table = lua.eval('{ name = "mlua", nested = { 1, 2, 3 } }')

    result = lua_2_python(table)

    assert result == {"name": "mlua", "nested": [1, 2, 3]}
