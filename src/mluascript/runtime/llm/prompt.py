"""LLM prompt 拼装"""

from __future__ import annotations

import json
from typing import Any

from .models import AIDecisionMember, AIInputItem, OpenAITool


def build_decision_messages(
    provider_name: str,
    inputs: list[AIInputItem],
    info_sources: list[AIDecisionMember],
    decision_members: list[AIDecisionMember],
    min_tools: int,
    max_tools: int,
) -> list[dict[str, Any]]:
    input_payload = []
    for item in inputs:
        payload: dict[str, Any] = {
            "kind": item.kind,
            "source": item.source,
            "value": item.value,
            "extra": item.extra,
        }
        image_url = item.extra.get("image_url") if isinstance(item.extra, dict) else None
        if item.kind == "image" and image_url:
            payload["value"] = image_url
        input_payload.append(payload)

    info_payload = []
    for item in info_sources:
        info_payload.append(
            {
                "id": item.id,
                "title": item.title,
                "description": item.description,
                "params": item.params,
                "tool_name": item.openai_tool.function.name if item.openai_tool else item.id,
            }
        )

    member_payload = []
    for item in decision_members:
        member_payload.append(
            {
                "id": item.id,
                "title": item.title,
                "description": item.description,
                "kind": item.kind,
            }
        )

    system_content = (
        "你是脚本 AI 决策器。"
        "你可以调用信息源工具获取信息。"
        "你必须从给定的候选决策成员中选择唯一结果。"
        "不要直接执行动作，只输出最终选择结果 JSON。"
    )
    user_content = {
        "provider": provider_name,
        "inputs": input_payload,
        "info_sources": info_payload,
        "decision_members": member_payload,
        "min_tools": min_tools,
        "max_tools": max_tools,
        "return_json_schema": {
            "selected_member_id": "string",
            "reason": "string",
        },
    }
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": json.dumps(user_content, ensure_ascii=False)},
    ]


def build_tool_specs(info_sources: list[AIDecisionMember]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for item in info_sources:
        if item.openai_tool is not None:
            specs.append(item.openai_tool.model_dump(by_alias=True, exclude_none=True))
            continue
        specs.append(_build_legacy_tool_spec(item).model_dump(by_alias=True, exclude_none=True))
    return specs


def _build_legacy_tool_spec(item: AIDecisionMember) -> OpenAITool:
    params_properties: dict[str, Any] = {}
    required: list[str] = []
    for param in item.params:
        name = str(param.get("name") or "").strip()
        if not name:
            continue
        params_properties[name] = {
            "type": str(param.get("type") or "string"),
            "description": str(param.get("description") or ""),
        }
        if param.get("required"):
            required.append(name)
    return OpenAITool.model_validate(
        {
            "type": "function",
            "function": {
                "name": item.id,
                "description": item.description or item.title or item.id,
                "parameters": {
                    "type": "object",
                    "properties": params_properties,
                    "required": required,
                },
            },
        }
    )
