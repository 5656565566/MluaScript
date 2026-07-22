from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .template_models import (
    TemplateCondition,
    TemplateMeta,
    TemplateSavedConfig,
    TemplateStepDef,
    TemplateSuccessBranchDef,
    TemplateTaskArgRef,
    TemplateTaskDef,
)
from .template_normalizer import is_condition_active


@dataclass(frozen=True, slots=True)
class RuntimeCondition:
    """运行时分支条件 保留模板条件的完整对外结构"""

    key: str
    eq: Any = None
    ne: Any = None
    gt: int | float | None = None
    gte: int | float | None = None
    lt: int | float | None = None
    lte: int | float | None = None
    in_values: tuple[Any, ...] = ()

    @classmethod
    def from_template(cls, condition: TemplateCondition) -> "RuntimeCondition":
        return cls(
            key=condition.k,
            eq=condition.eq,
            ne=condition.ne,
            gt=condition.gt,
            gte=condition.gte,
            lt=condition.lt,
            lte=condition.lte,
            in_values=tuple(condition.in_),
        )

    def selected_operator(self) -> tuple[str, Any] | None:
        """按现有优先级选择 Lua 运行时实际执行的条件操作符"""
        if self.in_values:
            return "in", list(self.in_values)
        for operator in ("gt", "gte", "lt", "lte", "ne", "eq"):
            expected = getattr(self, operator)
            if expected is not None:
                return operator, expected
        return None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"k": self.key}
        for operator in ("eq", "ne", "gt", "gte", "lt", "lte"):
            expected = getattr(self, operator)
            if expected is not None:
                payload[operator] = expected
        # Pydantic 的原始 model_dump 会保留空 in 列表 此处保持既有返回结构
        payload["in"] = list(self.in_values)
        return payload


@dataclass(frozen=True, slots=True)
class RuntimeBranch:
    """成功后根据任务流参数跳转的运行时分支"""

    condition: RuntimeCondition
    target_step_key: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "if": self.condition.to_payload(),
            "goto": self.target_step_key,
        }


@dataclass(frozen=True, slots=True)
class RuntimeTransition:
    """步骤完成后的动作及可选跳转目标"""

    action: str
    target_step_key: str


@dataclass(frozen=True, slots=True)
class RuntimeStep:
    """完成参数合并和条件过滤后的运行时步骤"""

    key: str
    task_key: str
    function_name: str
    enabled: bool
    arguments: dict[str, Any]
    success_branches: tuple[RuntimeBranch, ...]
    on_success: RuntimeTransition
    on_failure: RuntimeTransition

    def to_payload(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "task": self.task_key,
            "fn": self.function_name,
            "enabled": self.enabled,
            "args": dict(self.arguments),
            "successBranches": [branch.to_payload() for branch in self.success_branches],
            "onSuccess": self.on_success.action,
            "successGoto": self.on_success.target_step_key,
            "onFail": self.on_failure.action,
            "goto": self.on_failure.target_step_key,
        }


@dataclass(frozen=True, slots=True)
class RuntimeFlow:
    """可直接交给 Lua 代码生成器的强类型任务流"""

    key: str
    steps: tuple[RuntimeStep, ...]
    globals: dict[str, Any]
    lock_steps: bool

    def to_payload(self) -> dict[str, Any]:
        """转换为现有 Web 和 TUI 调用方使用的兼容字典"""
        return {
            "flowKey": self.key,
            "steps": [step.to_payload() for step in self.steps],
            "globals": dict(self.globals),
            "lockSteps": self.lock_steps,
        }


class RuntimeFlowBuilder:
    """将模板元数据和用户配置规划为稳定的运行时任务流"""

    def __init__(self, meta: TemplateMeta, saved: TemplateSavedConfig) -> None:
        self._meta = meta
        self._saved = saved

    def build(self, *, flow_key: str) -> RuntimeFlow:
        flow = next((item for item in self._meta.flows if item.k == flow_key), None)
        if flow is None:
            raise KeyError(flow_key)

        saved_flow = self._saved.flows.get(flow_key)
        saved_globals = dict(saved_flow.globals if saved_flow else {})
        global_values = {
            key: _normalize_runtime_value(self._meta.vars.get(key), saved_globals.get(key, self._meta.vars[key].def_))
            for key in flow.g
            if key in self._meta.vars
        }
        template_values = {key: field.def_ for key, field in self._meta.vars.items()}
        template_values.update(global_values)

        step_enabled = dict(saved_flow.stepEnabled if saved_flow else {})
        step_arguments = dict(saved_flow.stepArgs if saved_flow else {})
        ordered_steps = self._order_steps(flow.steps, flow.lockSteps, saved_flow.stepOrder if saved_flow else [])
        task_map = {task.k: task for task in self._meta.tasks}
        step_keys = {step.k for step in flow.steps}

        runtime_steps = tuple(
            self._build_step(
                step,
                task_map=task_map,
                step_keys=step_keys,
                step_enabled=step_enabled,
                saved_step_arguments=step_arguments,
                template_values=template_values,
                lock_steps=flow.lockSteps,
            )
            for step in ordered_steps
        )
        return RuntimeFlow(
            key=flow.k,
            steps=runtime_steps,
            globals=global_values,
            lock_steps=flow.lockSteps,
        )

    @staticmethod
    def _order_steps(
        steps: list[TemplateStepDef],
        lock_steps: bool,
        saved_order: list[str],
    ) -> list[TemplateStepDef]:
        step_order = list(saved_order if not lock_steps and saved_order else [step.k for step in steps])
        order_map = {key: index for index, key in enumerate(step_order)}
        original_order = {step.k: index for index, step in enumerate(steps)}
        return sorted(
            steps,
            key=lambda item: order_map.get(item.k, len(order_map) + original_order.get(item.k, 0)),
        )

    def _build_step(
        self,
        step: TemplateStepDef,
        *,
        task_map: dict[str, TemplateTaskDef],
        step_keys: set[str],
        step_enabled: dict[str, bool],
        saved_step_arguments: dict[str, dict[str, Any]],
        template_values: dict[str, Any],
        lock_steps: bool,
    ) -> RuntimeStep:
        task = task_map.get(step.task)
        if task is None:
            raise ValueError(f"工作流步骤 {step.k} 引用了不存在的任务: {step.task}")

        on_success = RuntimeTransition(action=step.onSuccess, target_step_key=step.successGoto)
        on_failure = RuntimeTransition(action=step.onFail, target_step_key=step.goto)
        self._validate_transition(step.k, "成功", on_success, step_keys)
        self._validate_transition(step.k, "失败", on_failure, step_keys)

        enabled = step.enabled if lock_steps else step_enabled.get(step.k, step.enabled)
        arguments = self._build_arguments(
            task,
            step,
            saved_step_arguments.get(step.k, {}),
            template_values,
        )
        return RuntimeStep(
            key=step.k,
            task_key=task.k,
            function_name=task.fn,
            enabled=bool(enabled),
            arguments=arguments,
            success_branches=tuple(self._build_branch(branch, step_keys) for branch in step.successBranches),
            on_success=on_success,
            on_failure=on_failure,
        )

    def _build_arguments(
        self,
        task: TemplateTaskDef,
        step: TemplateStepDef,
        saved_arguments: dict[str, Any],
        template_values: dict[str, Any],
    ) -> dict[str, Any]:
        task_arguments: dict[str, TemplateTaskArgRef] = {
            argument if isinstance(argument, str) else argument.k: argument
            for argument in task.args
        }

        merged_values: dict[str, Any] = {}
        for field_key in task_arguments:
            field_definition = self._meta.vars.get(field_key)
            if field_definition is not None:
                merged_values[field_key] = field_definition.def_
        merged_values.update(
            {key: _resolve_template_binding(value, template_values) for key, value in task.defaults.items()}
        )
        merged_values.update(
            {key: _resolve_template_binding(value, template_values) for key, value in step.args.items()}
        )
        merged_values.update(saved_arguments)

        normalized_values = {
            key: _normalize_runtime_value(self._meta.vars.get(key), value)
            for key, value in merged_values.items()
        }
        injected_values: dict[str, Any] = {}
        for field_key, value in normalized_values.items():
            field_definition = self._meta.vars.get(field_key)
            if field_definition is None:
                injected_values[field_key] = value
                continue
            task_argument = task_arguments.get(field_key)
            condition = None if isinstance(task_argument, str) or task_argument is None else task_argument.if_
            if not is_condition_active(condition, normalized_values):
                continue
            injected_values[field_definition.as_ or field_key] = value
        return injected_values

    @staticmethod
    def _validate_transition(
        step_key: str,
        transition_name: str,
        transition: RuntimeTransition,
        step_keys: set[str],
    ) -> None:
        if transition.action == "goto" and transition.target_step_key not in step_keys:
            raise ValueError(
                f"工作流步骤 {step_key} 的{transition_name}跳转目标不存在: {transition.target_step_key}"
            )

    @staticmethod
    def _build_branch(branch: TemplateSuccessBranchDef, step_keys: set[str]) -> RuntimeBranch:
        if branch.goto not in step_keys:
            raise ValueError(f"成功分支跳转目标不存在: {branch.goto}")
        return RuntimeBranch(
            condition=RuntimeCondition.from_template(branch.if_),
            target_step_key=branch.goto,
        )


def _resolve_template_binding(value: Any, template_values: dict[str, Any]) -> Any:
    """解析编辑器绑定描述符 同时保留旧版字面量值"""
    if not isinstance(value, dict) or "$bind" not in value:
        return value
    source = value.get("$bind")
    if source == "literal":
        return value.get("value")
    if source == "var":
        return template_values.get(str(value.get("key") or ""))
    return value


def _normalize_runtime_value(field_def: Any, value: Any) -> Any:
    """将编辑器编码的 JSON 字符串转换为实际运行时值"""
    if field_def is None or field_def.tp != "json" or not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 保留原始值 以便现有的校验和错误报告流程能够识别
        # 导致问题的输入 而不会在不提示的情况下修改其内容
        return value
