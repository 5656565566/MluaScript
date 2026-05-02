import json
from typing import Any

from lupa.lua54 import LuaRuntime

def python_2_lua(lua_runtime: LuaRuntime, data: Any) -> Any:
    """Python 对象转 Lua 表格"""
    if isinstance(data, (tuple, list, set)):
        table = lua_runtime.table()
        for i, item in enumerate(data, start=1):
            table[i] = python_2_lua(lua_runtime, item)
        return table

    if isinstance(data, dict):
        table = lua_runtime.table()
        for key, value in data.items():
            table[key] = python_2_lua(lua_runtime, value)
        return table

    return data


def lua_2_python(value: Any, visited: set[int] | None = None) -> Any:
    """将 Lua table 值递归转为 Python 原生结构"""
    if visited is None:
        visited = set()

    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, list):
        return [lua_2_python(item, visited) for item in value]
    if isinstance(value, tuple):
        return [lua_2_python(item, visited) for item in value]
    if isinstance(value, dict):
        return {str(key): lua_2_python(val, visited) for key, val in value.items()}

    has_items = hasattr(value, "items")
    has_len = hasattr(value, "__len__")
    has_getitem = hasattr(value, "__getitem__")
    if has_items and has_len and has_getitem:
        object_id = id(value)
        if object_id in visited:
            return "<recursive lua table>"
        visited.add(object_id)
        try:
            keys = list(value.keys()) if hasattr(value, "keys") else []
            is_array_like = bool(keys) and all(isinstance(key, int) for key in keys)
            if is_array_like:
                ordered_keys = sorted(keys)
                if ordered_keys == list(range(1, len(ordered_keys) + 1)):
                    return [lua_2_python(value[key], visited) for key in ordered_keys]
            return {
                str(key): lua_2_python(value[key], visited)
                for key in keys
            }
        except Exception:
            return str(value)
        finally:
            visited.discard(object_id)

    return str(value)


def format_lua_value(value: Any, visited: set[int] | None = None) -> str:
    """将 Lua 值格式化为便于阅读的字符串"""
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
    normalized = lua_2_python(value, visited)
    if isinstance(normalized, (list, dict)):
        return json.dumps(normalized, ensure_ascii=False, indent=2)
    return str(normalized)