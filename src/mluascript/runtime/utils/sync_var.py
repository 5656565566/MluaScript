import json
import threading
from typing import Any

from lupa.lua54 import LuaRuntime

from .table_lua import python_2_lua


class SyncVar:
    """
    跨线程安全变量存储实例

    内部统一保存 Python 原生结构
    读取时可按当前 LuaRuntime 自动转回 Lua table
    让 Lua 侧对复杂对象的访问尽量接近原生语义
    """

    def __init__(self, initial: Any = None) -> None:
        self._lock = threading.RLock()
        self._value = self._normalize(initial)

    def _normalize(self, value: Any) -> Any:
        """将 Lua table 或其他类型转为 Python 原生类型"""
        if hasattr(value, "items") and hasattr(value, "keys") and not isinstance(value, dict):
            try:
                keys = list(value.keys())
                is_array = bool(keys) and all(isinstance(k, int) for k in keys)
                if is_array:
                    sorted_keys = sorted(keys)
                    if sorted_keys == list(range(1, len(sorted_keys) + 1)):
                        return [self._normalize(value[k]) for k in sorted_keys]
                return {
                    self._normalize(k): self._normalize(value[k])
                    for k in keys
                }
            except Exception:
                pass

        if isinstance(value, dict):
            return {self._normalize(k): self._normalize(v) for k, v in value.items()}

        if isinstance(value, (list, tuple)):
            return [self._normalize(item) for item in value]

        if isinstance(value, set):
            return [self._normalize(item) for item in value]

        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")

        if isinstance(value, (str, int, float, bool)) or value is None:
            return value

        if hasattr(value, "__len__") and hasattr(value, "__getitem__") and not isinstance(value, str):
            try:
                return [self._normalize(item) for item in list(value)]
            except Exception:
                pass

        return value

    def _to_lua_value(self, lua_runtime: LuaRuntime | None, value: Any) -> Any:
        if lua_runtime is None:
            return value
        return python_2_lua(lua_runtime, value)

    def get(self, lua_runtime: LuaRuntime | None = None) -> Any:
        with self._lock:
            return self._to_lua_value(lua_runtime, self._value)

    def set(self, value: Any) -> Any:
        normalized = self._normalize(value)
        with self._lock:
            self._value = normalized
            return self._value

    def clear(self) -> None:
        with self._lock:
            self._value = None

    def update(self, value: Any = None, **kwargs: Any) -> Any:
        with self._lock:
            if not isinstance(self._value, dict):
                self._value = {}
            if value is not None:
                normalized = self._normalize(value)
                if isinstance(normalized, dict):
                    self._value.update(normalized)
                else:
                    raise TypeError("SyncVar.update only supports table/dict type parameters")
            if kwargs:
                self._value.update({k: self._normalize(v) for k, v in kwargs.items()})
            return self._value

    def append(self, value: Any) -> Any:
        with self._lock:
            if self._value is None:
                self._value = []
            if not isinstance(self._value, list):
                raise TypeError("SyncVar.append only supports list/array type")
            self._value.append(self._normalize(value))
            return self._value

    def extend(self, values: Any) -> Any:
        with self._lock:
            if self._value is None:
                self._value = []
            if not isinstance(self._value, list):
                raise TypeError("SyncVar.extend only supports list/array type")
            normalized = self._normalize(values)
            if not isinstance(normalized, list):
                raise TypeError("SyncVar.extend parameter must be list/array")
            self._value.extend(normalized)
            return self._value

    def get_key(self, key: Any, default: Any = None, lua_runtime: LuaRuntime | None = None) -> Any:
        key = self._normalize(key)
        with self._lock:
            result = default
            if isinstance(self._value, dict):
                result = self._value.get(key, default)
            elif isinstance(self._value, list) and isinstance(key, int):
                index = key - 1
                if 0 <= index < len(self._value):
                    result = self._value[index]
            return self._to_lua_value(lua_runtime, result)

    def set_key(self, key: Any, value: Any) -> Any:
        key = self._normalize(key)
        normalized = self._normalize(value)
        with self._lock:
            if isinstance(self._value, dict):
                self._value[key] = normalized
                return normalized
            if isinstance(self._value, list) and isinstance(key, int):
                index = key - 1
                while len(self._value) <= index:
                    self._value.append(None)
                self._value[index] = normalized
                return normalized
            if self._value is None:
                self._value = {key: normalized}
                return normalized
            raise TypeError("Current SyncVar is not table/dict or array type")

    def size(self) -> int:
        with self._lock:
            if self._value is None:
                return 0
            if hasattr(self._value, "__len__"):
                return len(self._value)
            return 0

    def is_nil(self) -> bool:
        with self._lock:
            return self._value is None

    def to_json(self) -> str:
        with self._lock:
            return json.dumps(self._value, ensure_ascii=False)


class LuaSyncVar:
    """
    面向 Lua 暴露的同步变量代理
    保持写入仍走 SyncVar 的线程安全存储
    读取时自动绑定当前 LuaRuntime 把 Python 结构转回 Lua table
    """

    def __init__(self, sync_var: SyncVar, lua_runtime: LuaRuntime) -> None:
        self._sync_var = sync_var
        self._lua = lua_runtime

    def get(self) -> Any:
        return self._sync_var.get(self._lua)

    def set(self, value: Any) -> Any:
        return self._sync_var.set(value)

    def clear(self) -> None:
        self._sync_var.clear()

    def update(self, value: Any = None, **kwargs: Any) -> Any:
        return self._sync_var.update(value, **kwargs)

    def append(self, value: Any) -> Any:
        return self._sync_var.append(value)

    def extend(self, values: Any) -> Any:
        return self._sync_var.extend(values)

    def get_key(self, key: Any, default: Any = None) -> Any:
        return self._sync_var.get_key(key, default)

    def set_key(self, key: Any, value: Any) -> Any:
        return self._sync_var.set_key(key, value)

    def size(self) -> int:
        return self._sync_var.size()

    def is_nil(self) -> bool:
        return self._sync_var.is_nil()

    def to_json(self) -> str:
        return self._sync_var.to_json()
