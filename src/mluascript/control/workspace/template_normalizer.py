from __future__ import annotations

from copy import deepcopy
from typing import Any

from .template_models import (
    TemplateCondition,
    TemplateFlowDef,
    TemplateMeta,
    TemplateOptionDef,
    TemplateStepDef,
    TemplateTaskDef,
    TemplateVarDef,
)

_TOP_LEVEL_ALIASES = {
    "version": "v",
    "title": "t",
    "description": "d",
    "userTitle": "ut",
    "userDescription": "ud",
    "taskCatalog": "tasks",
    "workflows": "flows",
}


class TemplateNormalizeError(ValueError):
    """模板标准化异常"""


def normalize_template_meta(raw_meta: dict[str, Any] | TemplateMeta | None) -> TemplateMeta:
    """将作者层模板声明标准化为系统内部扁平结构"""
    if raw_meta is None:
        return TemplateMeta()
    if isinstance(raw_meta, TemplateMeta):
        return raw_meta
    if not isinstance(raw_meta, dict):
        raise TemplateNormalizeError("模板元数据必须是对象")

    payload = _normalize_top_level_aliases(raw_meta)
    vars_payload = payload.get("vars")
    payload["vars"], legacy_relations = _normalize_vars(vars_payload)
    payload["tasks"] = [_normalize_task(item) for item in _ensure_list(payload.get("tasks"))]
    _attach_legacy_relations_to_tasks(payload["tasks"], legacy_relations)
    payload["flows"] = [_normalize_flow(item) for item in _ensure_list(payload.get("flows"))]
    return TemplateMeta.model_validate(payload)


def _normalize_top_level_aliases(raw_meta: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(raw_meta)
    for alias, target in _TOP_LEVEL_ALIASES.items():
        if alias in payload and target not in payload:
            payload[target] = payload.pop(alias)
    return payload


def _normalize_task(raw_task: Any) -> dict[str, Any]:
    if isinstance(raw_task, TemplateTaskDef):
        return raw_task.model_dump(by_alias=True)
    if not isinstance(raw_task, dict):
        raise TemplateNormalizeError("tasks 项必须是对象")
    payload = deepcopy(raw_task)
    if "key" in payload and "k" not in payload:
        payload["k"] = payload.pop("key")
    if "title" in payload and "t" not in payload:
        payload["t"] = payload.pop("title")
    if "description" in payload and "d" not in payload:
        payload["d"] = payload.pop("description")
    if "userTitle" in payload and "ut" not in payload:
        payload["ut"] = payload.pop("userTitle")
    if "userDescription" in payload and "ud" not in payload:
        payload["ud"] = payload.pop("userDescription")
    if "functionRef" in payload and "fn" not in payload:
        payload["fn"] = payload.pop("functionRef")
    if "option" in payload and "args" not in payload:
        payload["args"] = payload.pop("option")
    payload["args"] = [_normalize_task_arg(item) for item in _ensure_list(payload.get("args"))]
    return payload


def _normalize_task_arg(raw_arg: Any) -> str | dict[str, Any]:
    if isinstance(raw_arg, str):
        return raw_arg.strip()
    if not isinstance(raw_arg, dict):
        raise TemplateNormalizeError("task args 项必须是字段 key 或对象")
    payload = deepcopy(raw_arg)
    if "key" in payload and "k" not in payload:
        payload["k"] = payload.pop("key")
    if "visibleWhen" in payload and "if" not in payload:
        payload["if"] = payload.pop("visibleWhen")
    if "if" in payload and isinstance(payload["if"], dict):
        condition = dict(payload["if"])
        if "key" in condition and "k" not in condition:
            condition["k"] = condition.pop("key")
        payload["if"] = condition
    return payload


def _normalize_flow(raw_flow: Any) -> dict[str, Any]:
    if isinstance(raw_flow, TemplateFlowDef):
        return raw_flow.model_dump(by_alias=True)
    if not isinstance(raw_flow, dict):
        raise TemplateNormalizeError("flows 项必须是对象")
    payload = deepcopy(raw_flow)
    if "key" in payload and "k" not in payload:
        payload["k"] = payload.pop("key")
    if "title" in payload and "t" not in payload:
        payload["t"] = payload.pop("title")
    if "description" in payload and "d" not in payload:
        payload["d"] = payload.pop("description")
    if "userTitle" in payload and "ut" not in payload:
        payload["ut"] = payload.pop("userTitle")
    if "userDescription" in payload and "ud" not in payload:
        payload["ud"] = payload.pop("userDescription")
    if "globals" in payload and "g" not in payload:
        payload["g"] = payload.pop("globals")
    if "tasks" in payload and "steps" not in payload:
        payload["steps"] = payload.pop("tasks")
    payload["steps"] = [_normalize_step(item) for item in _ensure_list(payload.get("steps"))]
    return payload


def _normalize_step(raw_step: Any) -> dict[str, Any]:
    if isinstance(raw_step, TemplateStepDef):
        return raw_step.model_dump(by_alias=True)
    if not isinstance(raw_step, dict):
        raise TemplateNormalizeError("steps 项必须是对象")
    payload = deepcopy(raw_step)
    if "key" in payload and "k" not in payload:
        payload["k"] = payload.pop("key")
    if "title" in payload and "t" not in payload:
        payload["t"] = payload.pop("title")
    if "description" in payload and "d" not in payload:
        payload["d"] = payload.pop("description")
    if "userTitle" in payload and "ut" not in payload:
        payload["ut"] = payload.pop("userTitle")
    if "userDescription" in payload and "ud" not in payload:
        payload["ud"] = payload.pop("userDescription")
    if "taskRef" in payload and "task" not in payload:
        payload["task"] = payload.pop("taskRef")
    return payload


def _normalize_vars(raw_vars: Any) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    if raw_vars is None:
        return {}, {}
    relations: dict[str, dict[str, Any]] = {}
    if isinstance(raw_vars, dict):
        flattened: dict[str, dict[str, Any]] = {}
        for key, item in raw_vars.items():
            payload = _normalize_var_payload(item, fallback_key=key)
            _collect_var(payload, flattened, relations, parent=None, parent_value=None)
        return flattened, relations
    if isinstance(raw_vars, list):
        flattened = {}
        for item in raw_vars:
            payload = _normalize_var_payload(item, fallback_key="")
            _collect_var(payload, flattened, relations, parent=None, parent_value=None)
        return flattened, relations
    raise TemplateNormalizeError("vars 必须是对象或数组")


def _normalize_var_payload(raw_var: Any, *, fallback_key: str) -> dict[str, Any]:
    if isinstance(raw_var, TemplateVarDef):
        payload = raw_var.model_dump(by_alias=True)
    elif isinstance(raw_var, dict):
        payload = deepcopy(raw_var)
    else:
        raise TemplateNormalizeError("字段定义必须是对象")

    if fallback_key and not payload.get("k") and not payload.get("key"):
        payload["k"] = fallback_key

    alias_pairs = {
        "key": "k",
        "title": "t",
        "description": "d",
        "type": "tp",
        "default": "def",
        "required": "req",
        "pattern": "pat",
        "group": "grp",
        "options": "oneOf",
        "visibleWhen": "if",
    }
    for alias, target in alias_pairs.items():
        if alias in payload and target not in payload:
            payload[target] = payload.pop(alias)

    if "if" in payload and isinstance(payload["if"], dict):
        condition = dict(payload["if"])
        if "key" in condition and "k" not in condition:
            condition["k"] = condition.pop("key")
        payload["if"] = condition

    options = []
    for option in _ensure_list(payload.get("oneOf")):
        option_payload = _normalize_option_payload(option)
        options.append(option_payload)
    payload["oneOf"] = options
    payload["children"] = [_normalize_var_payload(item, fallback_key="") for item in _ensure_list(payload.get("children"))]
    return payload


def _normalize_option_payload(raw_option: Any) -> dict[str, Any]:
    if isinstance(raw_option, TemplateOptionDef):
        payload = raw_option.model_dump(by_alias=True)
    elif isinstance(raw_option, dict):
        payload = deepcopy(raw_option)
    else:
        payload = {"v": raw_option, "t": str(raw_option)}

    if "value" in payload and "v" not in payload:
        payload["v"] = payload.pop("value")
    if "label" in payload and "t" not in payload:
        payload["t"] = payload.pop("label")
    if "title" in payload and "t" not in payload:
        payload["t"] = payload.pop("title")
    payload["children"] = [_normalize_var_payload(item, fallback_key="") for item in _ensure_list(payload.get("children"))]
    return payload


def _collect_var(
    payload: dict[str, Any],
    flattened: dict[str, dict[str, Any]],
    relations: dict[str, dict[str, Any]],
    *,
    parent: str | None,
    parent_value: Any,
) -> None:
    key = str(payload.get("k") or "").strip()
    if not key:
        raise TemplateNormalizeError("字段缺少 k")
    if key in flattened:
        raise TemplateNormalizeError(f"字段重复: {key}")

    current = deepcopy(payload)
    child_items = current.pop("children", [])
    option_items = current.get("oneOf", [])

    relation: dict[str, Any] = {}
    if parent:
        relation["if"] = current.get("if") or {"k": parent, "eq": parent_value}
    else:
        if current.get("if"):
            relation["if"] = current["if"]
    if relation:
        relations[key] = relation
    current.pop("grp", None)
    current.pop("if", None)

    flattened[key] = current

    for child in child_items:
        _collect_var(child, flattened, relations, parent=key, parent_value=True)

    normalized_options = []
    for option in option_items:
        option_payload = deepcopy(option)
        nested_children = option_payload.pop("children", [])
        normalized_options.append(option_payload)
        for child in nested_children:
            _collect_var(child, flattened, relations, parent=key, parent_value=option_payload.get("v"))
    current["oneOf"] = normalized_options


def _task_arg_key(arg: str | dict[str, Any]) -> str:
    return arg if isinstance(arg, str) else str(arg.get("k") or "")


def _attach_legacy_relations_to_tasks(
    tasks: list[dict[str, Any]],
    relations: dict[str, dict[str, Any]],
) -> None:
    """Move legacy global parameter relationships into each compatible task."""
    for task in tasks:
        args = list(task.get("args") or [])
        task_keys = {_task_arg_key(arg) for arg in args}
        normalized_args: list[str | dict[str, Any]] = []
        for arg in args:
            key = _task_arg_key(arg)
            relation = relations.get(key)
            relation_parent = str((relation or {}).get("if", {}).get("k") or "")
            if not relation or not relation_parent or relation_parent not in task_keys:
                normalized_args.append(arg)
                continue
            if isinstance(arg, str):
                normalized_args.append({"k": key, **deepcopy(relation)})
            else:
                normalized = deepcopy(arg)
                for relation_key, value in relation.items():
                    normalized.setdefault(relation_key, deepcopy(value))
                normalized_args.append(normalized)
        task["args"] = normalized_args


def is_condition_active(condition: TemplateCondition | dict[str, Any] | None, values: dict[str, Any]) -> bool:
    if condition is None:
        return True
    cond = condition if isinstance(condition, TemplateCondition) else TemplateCondition.model_validate(condition)
    current = values.get(cond.k)
    if cond.in_:
        return current in cond.in_
    try:
        if cond.gt is not None:
            return current > cond.gt
        if cond.gte is not None:
            return current >= cond.gte
        if cond.lt is not None:
            return current < cond.lt
        if cond.lte is not None:
            return current <= cond.lte
    except TypeError:
        # 类型不匹配的比较条件不应中断模板规范化或运行。
        return False
    if cond.ne is not None:
        return current != cond.ne
    if "eq" in cond.model_fields_set or cond.eq is not None:
        return current == cond.eq
    return bool(current)


def _ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]
