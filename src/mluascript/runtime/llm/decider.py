"""LLM 决策运行时"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, TypeAdapter, ValidationError

from mluascript.shared.config import config as global_config

from ..image_bridge import RuntimeImageHandle
from .client import LLMClient
from .models import (
    AIDecisionMember,
    AIDecisionResult,
    AIMemberKind,
    AIInputItem,
    AIToolCallRecord,
    JsonSchemaObject,
    LLMConfig,
    OpenAITool,
    ToolExecutionResult,
)
from .prompt import build_decision_messages, build_tool_specs


class AIDecider:
    def __init__(self, provider: str = "", min_tools: int | None = None, max_tools: int | None = None) -> None:
        try:
            llm = global_config.get(LLMConfig)
        except RuntimeError:
            llm = LLMConfig()
        self.provider = provider or (llm.default_provider if llm else "")
        self.min_tools = llm.default_min_tools if min_tools is None and llm else int(min_tools or 0)
        self.max_tools = llm.default_max_tools if max_tools is None and llm else int(max_tools or 0)
        self.inputs: list[AIInputItem] = []
        self.members: list[AIDecisionMember] = []

    def add_text(self, text: Any) -> "AIDecider":
        self.inputs.append(AIInputItem(kind="text", value=str(text or ""), source="inline"))
        return self

    def add_screenshot(self, screenshot: Any = None, source: str = "screenshot") -> "AIDecider":
        extra: dict[str, Any] = {}
        if isinstance(screenshot, RuntimeImageHandle):
            png_bytes = screenshot.to_png_bytes()
            encoded = base64.b64encode(png_bytes).decode("ascii")
            extra = {
                "image_url": f"data:image/png;base64,{encoded}",
                "mime_type": "image/png",
                "width": screenshot.width,
                "height": screenshot.height,
            }
        self.inputs.append(AIInputItem(kind="image", value=screenshot, source=source or "screenshot", extra=extra))
        return self

    def add_image_file(self, path: str) -> "AIDecider":
        self.inputs.append(AIInputItem(kind="image_file", value=str(path or ""), source="file"))
        return self

    def add_member(
        self,
        member_id: str,
        description: str = "",
        *,
        kind: str = "choice_only",
        title: str = "",
        params: list[dict[str, Any]] | None = None,
        handler: Any = None,
        returns_to_ai: bool | None = None,
        enabled: bool = True,
        meta: dict[str, Any] | None = None,
        openai_tool: OpenAITool | dict[str, Any] | None = None,
        result_model: type[BaseModel] | None = None,
        result_type: Any = None,
        result_schema: JsonSchemaObject | dict[str, Any] | None = None,
    ) -> "AIDecider":
        normalized_id = str(member_id or "").strip()
        if not normalized_id:
            return self
        normalized_kind = str(kind or "choice_only").strip()
        normalized_result_schema = self._normalize_result_schema(result_schema)
        normalized_returns_to_ai = bool(returns_to_ai) if returns_to_ai is not None else bool(normalized_result_schema) or normalized_kind == "info_source"
        validated_tool = self._normalize_openai_tool(normalized_id, description, openai_tool)
        result_adapter = self._build_result_adapter(result_model=result_model, result_type=result_type)
        self.members.append(
            AIDecisionMember(
                id=normalized_id,
                title=str(title or "").strip(),
                description=str(description or "").strip(),
                kind=cast(AIMemberKind, normalized_kind),
                params=list(params or []),
                handler=handler,
                returns_to_ai=normalized_returns_to_ai,
                enabled=bool(enabled),
                meta=dict(meta or {}),
                openai_tool=validated_tool,
                result_model=result_model,
                result_adapter=result_adapter,
                result_schema=normalized_result_schema,
            )
        )
        return self

    def register_info_source(
        self,
        handler: Any,
        description: str = "",
        params: list[dict[str, Any]] | None = None,
        name: str = "",
        title: str = "",
        openai_tool: OpenAITool | dict[str, Any] | None = None,
        result_model: type[BaseModel] | None = None,
        result_type: Any = None,
        result_schema: JsonSchemaObject | dict[str, Any] | None = None,
    ) -> "AIDecider":
        member_id = str(name or getattr(handler, "__name__", "info_source")).strip() or "info_source"
        return self.add_member(
            member_id,
            description,
            kind="info_source",
            title=title or member_id,
            params=params,
            handler=handler,
            returns_to_ai=True,
            openai_tool=openai_tool,
            result_model=result_model,
            result_type=result_type,
            result_schema=result_schema,
        )

    def add_executor(
        self,
        handler: Any | None,
        description: str = "",
        *,
        member_id: str = "",
        title: str = "",
        params: list[dict[str, Any]] | None = None,
        meta: dict[str, Any] | None = None,
        openai_tool: OpenAITool | dict[str, Any] | None = None,
        result_model: type[BaseModel] | None = None,
        result_type: Any = None,
        result_schema: JsonSchemaObject | dict[str, Any] | None = None,
    ) -> "AIDecider":
        normalized_id = str(member_id or getattr(handler, "__name__", "executor")).strip() or "executor"
        return self.add_member(
            normalized_id,
            description,
            kind="executor",
            title=title or normalized_id,
            params=params,
            handler=handler,
            returns_to_ai=bool(result_schema),
            meta=meta,
            openai_tool=openai_tool,
            result_model=result_model,
            result_type=result_type,
            result_schema=result_schema,
        )

    def add_choice(self, choice_id: str, description: str = "", title: str = "") -> "AIDecider":
        return self.add_member(choice_id, description, kind="choice_only", title=title or choice_id)

    def _normalize_inputs(self) -> list[AIInputItem]:
        try:
            llm = global_config.get(LLMConfig)
        except RuntimeError:
            llm = LLMConfig()
        max_images = llm.max_input_image_count if llm else 2
        max_text_length = llm.max_input_text_length if llm else 4000
        normalized: list[AIInputItem] = []
        image_count = 0
        for item in self.inputs:
            if item.kind == "text":
                normalized.append(
                    AIInputItem(
                        kind=item.kind,
                        value=str(item.value or "")[:max_text_length],
                        source=item.source,
                        extra=item.extra,
                    )
                )
                continue
            if item.kind in {"image", "image_file"}:
                if image_count >= max_images:
                    continue
                value = item.value
                extra = dict(item.extra)
                if item.kind == "image_file":
                    value = str(Path(str(value or "")))
                normalized.append(AIInputItem(kind=item.kind, value=value, source=item.source, extra=extra))
                image_count += 1
        return normalized

    def _enabled_members(self) -> list[AIDecisionMember]:
        return [item for item in self.members if item.enabled]

    def _info_sources(self) -> list[AIDecisionMember]:
        return [item for item in self._enabled_members() if item.kind == "info_source"]

    def _decision_members(self) -> list[AIDecisionMember]:
        return [item for item in self._enabled_members() if item.kind in {"executor", "choice_only"}]

    def _find_member(self, member_id: str) -> AIDecisionMember | None:
        normalized_id = str(member_id or "").strip()
        if not normalized_id:
            return None
        for item in self._enabled_members():
            if item.id == normalized_id:
                return item
        return None

    def _normalize_openai_tool(
        self,
        member_id: str,
        description: str,
        openai_tool: OpenAITool | dict[str, Any] | None,
    ) -> OpenAITool | None:
        if openai_tool is None:
            return None
        validated = openai_tool if isinstance(openai_tool, OpenAITool) else OpenAITool.model_validate(openai_tool)
        if validated.function.name != member_id:
            raise ValueError(f"OpenAI tool name must match member id: {member_id}")
        if not validated.function.description:
            validated.function.description = str(description or member_id)
        return validated

    def _normalize_result_schema(self, result_schema: JsonSchemaObject | dict[str, Any] | None) -> JsonSchemaObject | None:
        if result_schema is None:
            return None
        return result_schema if isinstance(result_schema, JsonSchemaObject) else JsonSchemaObject.model_validate(result_schema)

    def _build_result_adapter(self, result_model: type[BaseModel] | None, result_type: Any = None) -> TypeAdapter[Any] | None:
        if result_model is not None:
            return TypeAdapter(result_model)
        if result_type is not None:
            return TypeAdapter(result_type)
        return None

    def _validate_against_result_schema(self, schema: JsonSchemaObject, result: Any, path: str = "result") -> str | None:
        schema_type = schema.type
        if isinstance(schema_type, list):
            errors = [self._validate_against_schema_type(candidate, schema, result, path) for candidate in schema_type]
            if any(error is None for error in errors):
                return None
            return "; ".join(error for error in errors if error)
        return self._validate_against_schema_type(schema_type, schema, result, path)

    def _validate_against_schema_type(
        self,
        schema_type: str | None,
        schema: JsonSchemaObject,
        result: Any,
        path: str,
    ) -> str | None:
        if schema.anyOf:
            errors = [self._validate_against_result_schema(candidate, result, path) for candidate in schema.anyOf]
            if any(error is None for error in errors):
                return None
            return "; ".join(error for error in errors if error)
        if schema.ref:
            return None
        if schema_type is None:
            return None
        if schema_type == "null":
            return None if result is None else f"{path} 应为 null"
        if schema_type == "string":
            return None if isinstance(result, str) else f"{path} 应为 string"
        if schema_type == "boolean":
            return None if isinstance(result, bool) else f"{path} 应为 boolean"
        if schema_type == "integer":
            if isinstance(result, bool) or not isinstance(result, int):
                return f"{path} 应为 integer"
            return None
        if schema_type == "number":
            if isinstance(result, bool) or not isinstance(result, (int, float)):
                return f"{path} 应为 number"
            return None
        if schema_type == "array":
            if not isinstance(result, list):
                return f"{path} 应为 array"
            if schema.minItems is not None and len(result) < schema.minItems:
                return f"{path} 至少包含 {schema.minItems} 项"
            if schema.maxItems is not None and len(result) > schema.maxItems:
                return f"{path} 至多包含 {schema.maxItems} 项"
            if schema.items is not None:
                for index, item in enumerate(result):
                    item_error = self._validate_against_result_schema(schema.items, item, f"{path}[{index}]")
                    if item_error:
                        return item_error
            return None
        if schema_type == "object":
            if not isinstance(result, dict):
                return f"{path} 应为 object"
            for key in schema.required:
                if key not in result:
                    return f"{path}.{key} 为必填字段"
            for key, value in result.items():
                property_schema = schema.properties.get(key)
                if property_schema is None:
                    continue
                item_error = self._validate_against_result_schema(property_schema, value, f"{path}.{key}")
                if item_error:
                    return item_error
            return None
        return None

    def _validate_result(self, member: AIDecisionMember, result: Any) -> ToolExecutionResult:
        adapter = member.result_adapter
        if adapter is not None:
            try:
                validated = adapter.validate_python(result)
            except ValidationError as exc:
                return ToolExecutionResult(value=result, validation_error=str(exc))
            if isinstance(validated, BaseModel):
                return ToolExecutionResult(value=validated.model_dump(mode="python"))
            return ToolExecutionResult(value=validated)
        if member.result_schema is not None:
            validation_error = self._validate_against_result_schema(member.result_schema, result)
            if validation_error:
                return ToolExecutionResult(value=result, validation_error=validation_error)
        return ToolExecutionResult(value=result)

    def _call_member(self, member: AIDecisionMember, arguments: dict[str, Any]) -> AIToolCallRecord:
        try:
            if callable(member.handler):
                result = member.handler(**arguments)
            else:
                result = None
            validated = self._validate_result(member, result)
            return AIToolCallRecord(
                member_id=member.id,
                member_kind=member.kind,
                arguments=arguments,
                success=validated.is_valid,
                result=validated.value,
                result_validation_error=validated.validation_error or "",
                error="" if validated.is_valid else (validated.validation_error or ""),
            )
        except Exception as exc:
            return AIToolCallRecord(
                member_id=member.id,
                member_kind=member.kind,
                arguments=arguments,
                success=False,
                result=None,
                error=str(exc),
            )

    def _extract_message_text(self, data: dict[str, Any]) -> str:
        choices = data.get("choices") or []
        if not isinstance(choices, list) or not choices:
            return ""
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(str(item.get("text") or ""))
            return "\n".join(part for part in text_parts if part)
        return ""

    def decide(self) -> AIDecisionResult:
        try:
            llm = global_config.get(LLMConfig)
        except RuntimeError:
            llm = LLMConfig()
        if not llm or not llm.enabled:
            return AIDecisionResult(success=False, provider=self.provider, reason="LLM 功能未启用", raw_text="")

        provider_name, provider = llm.get_provider(self.provider)
        if not provider_name or not provider:
            return AIDecisionResult(success=False, provider=self.provider, reason="未找到可用 LLM 提供源", raw_text="")

        info_sources = self._info_sources()
        decision_members = self._decision_members()
        if not decision_members:
            return AIDecisionResult(success=False, provider=provider_name, reason="未配置任何可选决策成员", raw_text="")

        normalized_inputs = self._normalize_inputs()
        messages = build_decision_messages(provider_name, normalized_inputs, info_sources, decision_members, self.min_tools, self.max_tools)
        tool_specs = build_tool_specs(info_sources)
        info_call_results: list[AIToolCallRecord] = []
        raw_text = ""

        try:
            client = LLMClient(provider_name, provider)
            data = client.create_completion(messages, tool_specs)
            raw_text = self._extract_message_text(data)
        except Exception as exc:
            return AIDecisionResult(success=False, provider=provider_name, reason=f"AI 请求失败: {exc}", raw_text=raw_text)

        parsed: dict[str, Any] = {}
        try:
            parsed = json.loads(raw_text) if raw_text else {}
        except Exception:
            pass

        selected_member_id = str(parsed.get("selected_member_id") or "").strip()
        if not selected_member_id:
            selected_member_id = decision_members[0].id
        reason = str(parsed.get("reason") or raw_text or "").strip()
        selected_member = self._find_member(selected_member_id) or decision_members[0]

        activation_limit = self.max_tools if self.max_tools > 0 else len(info_sources)
        selected_info_sources = info_sources[:activation_limit]
        if len(selected_info_sources) < self.min_tools:
            selected_info_sources = info_sources[: min(len(info_sources), self.min_tools)]

        for member in selected_info_sources:
            arguments = {}
            for param in member.params:
                param_name = str(param.get("name") or "").strip()
                if not param_name:
                    continue
                arguments[param_name] = param.get("default")
            info_call_results.append(self._call_member(member, arguments))

        executor_executed = False
        executor_result = None
        if selected_member.kind == "executor" and callable(selected_member.handler):
            executor_record = self._call_member(selected_member, {})
            executor_executed = True
            executor_result = executor_record.result if executor_record.success else {
                "error": executor_record.error,
                "result_validation_error": executor_record.result_validation_error,
            }

        return AIDecisionResult(
            success=True,
            provider=provider_name,
            selected_member_id=selected_member.id,
            selected_member_kind=selected_member.kind,
            selected_member_title=selected_member.title or selected_member.id,
            reason=reason,
            info_call_count=len(info_call_results),
            info_call_results=info_call_results,
            executor_executed=executor_executed,
            executor_result=executor_result,
            raw_text=raw_text,
        )
