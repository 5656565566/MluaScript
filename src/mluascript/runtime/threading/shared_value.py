from __future__ import annotations

from threading import Lock
from typing import Any

from lupa.lua54 import LuaRuntime

from ..utils.table_lua import lua_2_python, python_2_lua


class SharedValue:
    """线程安全共享值容器"""

    def __init__(self, initial: Any = None) -> None:
        self._lock = Lock()
        self._value = self._normalize(initial)

    def _normalize(self, value: Any) -> Any:
        return lua_2_python(value)

    def _to_lua(self, lua_runtime: LuaRuntime | None, value: Any) -> Any:
        if lua_runtime is None:
            return value
        return python_2_lua(lua_runtime, value)

    def get(self, lua_runtime: LuaRuntime | None = None) -> Any:
        with self._lock:
            return self._to_lua(lua_runtime, self._value)

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
                if not isinstance(normalized, dict):
                    raise TypeError("shared.value().update() only supports table/dict")
                self._value.update(normalized)
            if kwargs:
                self._value.update({k: self._normalize(v) for k, v in kwargs.items()})
            return self._value

    def append(self, value: Any) -> Any:
        with self._lock:
            if self._value is None:
                self._value = []
            if not isinstance(self._value, list):
                raise TypeError("shared.value().append() only supports list/array")
            self._value.append(self._normalize(value))
            return self._value

    def extend(self, values: Any) -> Any:
        normalized = self._normalize(values)
        with self._lock:
            if self._value is None:
                self._value = []
            if not isinstance(self._value, list):
                raise TypeError("shared.value().extend() only supports list/array")
            if not isinstance(normalized, list):
                raise TypeError("shared.value().extend() parameter must be list/array")
            self._value.extend(normalized)
            return self._value

    def get_key(self, key: Any, default: Any = None, lua_runtime: LuaRuntime | None = None) -> Any:
        normalized_key = self._normalize(key)
        with self._lock:
            result = default
            if isinstance(self._value, dict):
                result = self._value.get(normalized_key, default)
            elif isinstance(self._value, list) and isinstance(normalized_key, int):
                index = normalized_key - 1
                if 0 <= index < len(self._value):
                    result = self._value[index]
            return self._to_lua(lua_runtime, result)

    def set_key(self, key: Any, value: Any) -> Any:
        normalized_key = self._normalize(key)
        normalized_value = self._normalize(value)
        with self._lock:
            if isinstance(self._value, dict):
                self._value[normalized_key] = normalized_value
                return normalized_value
            if isinstance(self._value, list) and isinstance(normalized_key, int):
                index = normalized_key - 1
                while len(self._value) <= index:
                    self._value.append(None)
                self._value[index] = normalized_value
                return normalized_value
            if self._value is None:
                self._value = {normalized_key: normalized_value}
                return normalized_value
            raise TypeError("Current shared.value() is not table/dict or array")

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
            import json
            return json.dumps(self._value, ensure_ascii=False)


class LuaSharedValueView:
    """面向 Lua 暴露的共享值代理"""

    def __init__(self, shared_value: SharedValue, lua_runtime: LuaRuntime) -> None:
        self._shared_value = shared_value
        self._lua = lua_runtime

    def get(self) -> Any:
        return self._shared_value.get(self._lua)

    def set(self, value: Any) -> Any:
        return self._shared_value.set(value)

    def clear(self) -> None:
        self._shared_value.clear()

    def update(self, value: Any = None, **kwargs: Any) -> Any:
        return self._shared_value.update(value, **kwargs)

    def append(self, value: Any) -> Any:
        return self._shared_value.append(value)

    def extend(self, values: Any) -> Any:
        return self._shared_value.extend(values)

    def get_key(self, key: Any, default: Any = None) -> Any:
        return self._shared_value.get_key(key, default, self._lua)

    def set_key(self, key: Any, value: Any) -> Any:
        return self._shared_value.set_key(key, value)

    def size(self) -> int:
        return self._shared_value.size()

    def is_nil(self) -> bool:
        return self._shared_value.is_nil()

    def to_json(self) -> str:
        return self._shared_value.to_json()
