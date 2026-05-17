"""LLM Lua bridge"""

from __future__ import annotations

from typing import Any

from lupa.lua54 import LuaRuntime

from mluascript.shared.logging import logger

from .decider import AIDecider


class LuaDecisionResult:
    def __init__(self, lua_runtime: LuaRuntime, payload: dict[str, Any]) -> None:
        self._lua = lua_runtime
        self._payload = payload

    def to_table(self) -> Any:
        return self._lua.table_from(self._payload)


def _is_lua_mapping(value: Any) -> bool:
    return hasattr(value, "items") and hasattr(value, "keys")


def _lua_table_to_python(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_lua_table_to_python(item) for item in value]
    if isinstance(value, tuple):
        return [_lua_table_to_python(item) for item in value]
    if _is_lua_mapping(value):
        keys = list(value.keys())
        if keys and all(isinstance(key, (int, float)) for key in keys):
            numeric_keys = sorted(int(key) for key in keys)
            if numeric_keys == list(range(1, len(numeric_keys) + 1)):
                return [_lua_table_to_python(value[key]) for key in numeric_keys]
        return {str(key): _lua_table_to_python(value[key]) for key in keys}
    return value


def _normalize_params(params: Any) -> list[dict[str, Any]]:
    normalized_params: list[dict[str, Any]] = []
    converted = _lua_table_to_python(params)
    if isinstance(converted, list):
        normalized_params = [dict(item) for item in converted if isinstance(item, dict)]
    return normalized_params


def _normalize_mapping(value: Any) -> dict[str, Any]:
    converted = _lua_table_to_python(value)
    return converted if isinstance(converted, dict) else {}


class LuaAIDecider:
    def __init__(self, lua_runtime: LuaRuntime, provider: str = "", min_tools: int | None = None, max_tools: int | None = None) -> None:
        self._lua = lua_runtime
        self._decider = AIDecider(provider=provider, min_tools=min_tools, max_tools=max_tools)

    def add_text(self, text: Any) -> "LuaAIDecider":
        self._decider.add_text(text)
        return self

    def add_screenshot(self, screenshot: Any = None) -> "LuaAIDecider":
        self._decider.add_screenshot(screenshot)
        return self

    def add_image_file(self, path: str) -> "LuaAIDecider":
        self._decider.add_image_file(path)
        return self

    def add_info(self, config: Any) -> "LuaAIDecider":
        normalized = _normalize_mapping(config)
        handler = normalized.get("handler")
        if not callable(handler):
            raise ValueError("add_info.handler 必须是可调用函数")

        handler_name = getattr(handler, "__name__", None)
        if not handler_name:
            try:
                handler_name = str(getattr(handler, "name", "") or "")
            except Exception:
                handler_name = None
        member_id = str(normalized.get("name") or handler_name or "").strip() or "info_source"
        title = str(normalized.get("title") or member_id).strip()
        description = str(normalized.get("description") or "").strip()
        if not description:
            raise ValueError("add_info.description 为必填")

        properties = normalized.get("properties")
        required = normalized.get("required")
        returns = normalized.get("returns")

        openai_tool = {
            "type": "function",
            "function": {
                "name": member_id,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": properties if isinstance(properties, dict) else {},
                    "required": required if isinstance(required, list) else [],
                },
            },
        }

        self._decider.register_info_source(
            handler=handler,
            description=description,
            name=member_id,
            title=title,
            openai_tool=openai_tool,
            result_schema=returns if isinstance(returns, dict) else None,
        )
        return self

    def add_executor(self, config: Any) -> "LuaAIDecider":
        normalized = _normalize_mapping(config)
        handler = normalized.get("handler")
        if not callable(handler):
            raise ValueError("add_executor.handler 必须是可调用函数")

        handler_name = getattr(handler, "__name__", None)
        if not handler_name:
            try:
                handler_name = str(getattr(handler, "name", "") or "")
            except Exception:
                handler_name = None
        member_id = str(normalized.get("name") or handler_name or "").strip() or "executor"
        title = str(normalized.get("title") or member_id).strip()
        description = str(normalized.get("description") or "").strip()
        if not description:
            raise ValueError("add_executor.description 为必填")

        properties = normalized.get("properties")
        required = normalized.get("required")
        openai_tool = {
            "type": "function",
            "function": {
                "name": member_id,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": properties if isinstance(properties, dict) else {},
                    "required": required if isinstance(required, list) else [],
                },
            },
        }

        self._decider.add_executor(
            handler=handler,
            description=description,
            member_id=member_id,
            title=title,
            openai_tool=openai_tool,
        )
        return self

    def add_choice(self, choice_id: str, description: str = "", title: str = "") -> "LuaAIDecider":
        self._decider.add_choice(choice_id, description, title=title)
        return self

    def decide(self) -> Any:
        result = self._decider.decide()
        return LuaDecisionResult(self._lua, result.to_lua_payload()).to_table()


class LuaLLMExports:
    def __init__(self, lua_runtime: LuaRuntime) -> None:
        self._lua = lua_runtime

    def new_decider(self, provider: str = "", min_tools: int | None = None, max_tools: int | None = None) -> LuaAIDecider:
        return LuaAIDecider(self._lua, provider=provider, min_tools=min_tools, max_tools=max_tools)


def build_llm_exports(lua_runtime: LuaRuntime) -> LuaLLMExports:
    exports = LuaLLMExports(lua_runtime)
    logger.debug("LLM Exports 已创建")
    return exports
