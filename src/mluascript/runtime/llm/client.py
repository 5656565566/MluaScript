"""LLM HTTP 客户端"""

from __future__ import annotations

from typing import Any

import httpx

from .models import LLMProviderConfig

class LLMClient:
    def __init__(self, provider_name: str, provider: LLMProviderConfig) -> None:
        self.provider_name = provider_name
        self.provider = provider

    def build_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }
        if self.provider.api_key:
            headers["Authorization"] = f"Bearer {self.provider.api_key}"
        headers.update(self.provider.extra_headers)
        return headers

    def build_payload(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.provider.model,
            "messages": messages,
            "temperature": self.provider.temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        if self.provider.extra_body:
            payload.update(self.provider.extra_body)
        return payload

    def create_completion(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        with httpx.Client(timeout=self.provider.timeout) as client:
            response = client.post(
                self.provider.base_url,
                headers=self.build_headers(),
                json=self.build_payload(messages, tools),
            )
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else {}
