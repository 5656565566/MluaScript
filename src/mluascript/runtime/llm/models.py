"""LLM 运行时数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from mluascript.shared.config import config

AIMemberKind = Literal["info_source", "executor", "choice_only"]
JSONSchemaType = Literal[
    "string",
    "number",
    "integer",
    "boolean",
    "object",
    "array",
    "null",
]


class LLMProviderConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool = Field(default=True, description="是否启用该 LLM 提供源")
    base_url: str = Field(default="https://api.openai.com/v1/chat/completions", description="OpenAI 兼容接口地址")
    api_key: str = Field(default="", description="接口密钥")
    model: str = Field(default="gpt-4o-mini", description="模型名称")
    timeout: float = Field(default=30.0, ge=1.0, description="请求超时秒数")
    temperature: float = Field(default=0.2, ge=0.0, le=2.0, description="采样温度")
    max_retries: int = Field(default=1, ge=0, description="失败重试次数")
    extra_headers: dict[str, str] = Field(default_factory=dict, description="附加请求头")
    extra_body: dict[str, Any] = Field(default_factory=dict, description="附加请求体字段")


@config.registry()
class LLMConfig(BaseModel):
    """LLM 决策配置"""

    model_config = ConfigDict(extra="allow")

    enabled: bool = Field(default=False, description="是否启用 LLM 决策功能")
    default_provider: str = Field(default="openai-compatible", description="默认提供源名称")
    default_max_tools: int = Field(default=3, ge=0, description="默认最多激活工具数量")
    default_min_tools: int = Field(default=0, ge=0, description="默认最少激活工具数量")
    max_input_image_count: int = Field(default=2, ge=0, description="单次决策最多图片输入数")
    max_input_text_length: int = Field(default=4000, ge=1, description="单次决策文本输入最大长度")
    providers: dict[str, LLMProviderConfig] = Field(
        default_factory=lambda: {
            "openai-compatible": LLMProviderConfig(
                enabled=False,
                base_url="https://api.openai.com/v1/chat/completions",
                api_key="",
                model="gpt-4o-mini",
            )
        },
        description="可用提供源配置",
    )

    @model_validator(mode="after")
    def validate_defaults(self) -> LLMConfig:
        if self.default_provider and self.default_provider not in self.providers:
            raise ValueError(f"llm.default_provider not defined in providers: {self.default_provider}")
        if self.default_min_tools > self.default_max_tools:
            raise ValueError("llm.default_min_tools cannot be greater than llm.default_max_tools")
        return self

    def get_provider(self, name: str | None = None) -> tuple[str | None, LLMProviderConfig | None]:
        provider_name = (name or self.default_provider or "").strip()
        if not provider_name:
            return None, None
        provider = self.providers.get(provider_name)
        if not provider or not provider.enabled:
            return None, None
        return provider_name, provider

    def list_available_provider_names(self) -> list[str]:
        return [name for name, provider in self.providers.items() if provider.enabled]


class JsonSchemaObject(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    type: JSONSchemaType | list[JSONSchemaType] | None = None
    description: str | None = None
    enum: list[Any] | None = None
    default: Any = None
    format: str | None = None
    minimum: float | int | None = None
    maximum: float | int | None = None
    exclusiveMinimum: bool | float | int | None = None
    exclusiveMaximum: bool | float | int | None = None
    minLength: int | None = Field(default=None, ge=0)
    maxLength: int | None = Field(default=None, ge=0)
    minItems: int | None = Field(default=None, ge=0)
    maxItems: int | None = Field(default=None, ge=0)
    properties: dict[str, JsonSchemaObject] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)
    items: JsonSchemaObject | None = None
    anyOf: list[JsonSchemaObject] = Field(default_factory=list)
    ref: str | None = Field(default=None, alias="$ref")
    additionalProperties: bool | JsonSchemaObject | None = None


JsonSchemaObject.model_rebuild()


class OpenAIToolFunction(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1)
    description: str = ""
    strict: bool | None = None
    parameters: JsonSchemaObject = Field(default_factory=lambda: JsonSchemaObject(type="object"))


class OpenAITool(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Literal["function"] = "function"
    function: OpenAIToolFunction


class ToolExecutionResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    value: Any = None
    validation_error: str | None = None

    @property
    def is_valid(self) -> bool:
        return not self.validation_error


@dataclass(slots=True)
class AIInputItem:
    kind: str
    value: Any = None
    source: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AIDecisionMember:
    id: str
    title: str = ""
    description: str = ""
    kind: AIMemberKind = "choice_only"
    params: list[dict[str, Any]] = field(default_factory=list)
    handler: Callable[..., Any] | None = None
    returns_to_ai: bool = False
    enabled: bool = True
    meta: dict[str, Any] = field(default_factory=dict)
    openai_tool: OpenAITool | None = None
    result_model: type[BaseModel] | None = None
    result_adapter: TypeAdapter[Any] | None = None
    result_schema: JsonSchemaObject | None = None


@dataclass(slots=True)
class AIToolCallRecord:
    member_id: str
    member_kind: AIMemberKind
    arguments: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    result: Any = None
    error: str = ""
    result_validation_error: str = ""


@dataclass(slots=True)
class AIDecisionResult:
    success: bool = True
    provider: str = ""
    selected_member_id: str = ""
    selected_member_kind: AIMemberKind | str = "choice_only"
    selected_member_title: str = ""
    reason: str = ""
    info_call_count: int = 0
    info_call_results: list[AIToolCallRecord] = field(default_factory=list)
    executor_executed: bool = False
    executor_result: Any = None
    raw_text: str = ""

    def to_lua_payload(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "provider": self.provider,
            "selected_member_id": self.selected_member_id,
            "selected_member_kind": self.selected_member_kind,
            "selected_member_title": self.selected_member_title,
            "reason": self.reason,
            "info_call_count": self.info_call_count,
            "info_call_results": [
                {
                    "member_id": item.member_id,
                    "member_kind": item.member_kind,
                    "arguments": item.arguments,
                    "success": item.success,
                    "result": item.result,
                    "error": item.error,
                    "result_validation_error": item.result_validation_error,
                }
                for item in self.info_call_results
            ],
            "executor_executed": self.executor_executed,
            "executor_result": self.executor_result,
            "raw_text": self.raw_text,
        }
