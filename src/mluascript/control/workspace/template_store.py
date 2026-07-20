from __future__ import annotations

import json
import keyword
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .manager import WorkspaceManager, get_workspace_manager
from .template_models import TemplateMeta, TemplateSavedConfig
from .template_normalizer import is_condition_active
from .template_parser import parse_template_meta


class TemplateStore:
    """模板元数据读取与用户配置持久化"""

    def __init__(self, workspace_manager: WorkspaceManager | None = None) -> None:
        self.workspace_manager = workspace_manager or get_workspace_manager()

    def get_template_meta(self, script_path: str) -> TemplateMeta | None:
        text = self.workspace_manager.read_script(script_path)
        source = parse_template_meta(text, script_path=script_path)
        return source.meta if source else None

    def get_saved_config_path(self, script_path: str) -> str:
        script_file = self.workspace_manager._resolve_workspace_path(script_path)
        config_dir = self.workspace_manager.root_dir / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        return str((config_dir / f"{script_file.stem}.template.yaml").resolve())

    def load_saved_config(self, script_path: str) -> TemplateSavedConfig:
        config_path = Path(self.get_saved_config_path(script_path))
        if not config_path.exists():
            return TemplateSavedConfig(scriptPath=script_path)
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            return TemplateSavedConfig(scriptPath=script_path)
        payload = dict(raw)
        payload.setdefault("scriptPath", script_path)
        return TemplateSavedConfig.model_validate(payload)

    def save_saved_config(self, script_path: str, config: TemplateSavedConfig | dict[str, Any]) -> TemplateSavedConfig:
        normalized = config if isinstance(config, TemplateSavedConfig) else TemplateSavedConfig.model_validate(config)
        normalized.scriptPath = script_path
        normalized.updatedAt = datetime.now(timezone.utc).isoformat()
        config_path = Path(self.get_saved_config_path(script_path))
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            yaml.safe_dump(normalized.model_dump(exclude_none=True), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return normalized

    def build_runtime_payload(self, meta: TemplateMeta, saved: TemplateSavedConfig, *, flow_key: str) -> dict[str, Any]:
        flow = next((item for item in meta.flows if item.k == flow_key), None)
        if flow is None:
            raise KeyError(flow_key)
        saved_flow = saved.flows.get(flow_key)
        saved_globals = dict(saved_flow.globals if saved_flow else {})
        globals_values = {
            key: _normalize_runtime_value(meta.vars.get(key), saved_globals.get(key, meta.vars[key].def_))
            for key in flow.g
            if key in meta.vars
        }
        step_enabled = dict(saved_flow.stepEnabled if saved_flow else {})
        step_args = dict(saved_flow.stepArgs if saved_flow else {})
        step_order = list(
            saved_flow.stepOrder
            if not flow.lockSteps and saved_flow and saved_flow.stepOrder
            else [step.k for step in flow.steps]
        )
        template_values = {key: field.def_ for key, field in meta.vars.items()}
        template_values.update(globals_values)

        task_map = {task.k: task for task in meta.tasks}
        steps = []
        order_map = {key: idx for idx, key in enumerate(step_order)}
        original_order = {step.k: idx for idx, step in enumerate(flow.steps)}
        ordered_steps = sorted(flow.steps, key=lambda item: order_map.get(item.k, len(order_map) + original_order.get(item.k, 0)))
        for step in ordered_steps:
            task = task_map.get(step.task)
            if task is None:
                continue
            task_args = {
                arg if isinstance(arg, str) else arg.k: arg
                for arg in task.args
            }
            enabled = step.enabled if flow.lockSteps else step_enabled.get(step.k, step.enabled)
            merged = {}
            for field_key in task_args:
                field_def = meta.vars.get(field_key)
                if field_def is None:
                    continue
                merged[field_key] = field_def.def_
            merged.update({key: _resolve_template_binding(value, template_values) for key, value in task.defaults.items()})
            merged.update({key: _resolve_template_binding(value, template_values) for key, value in step.args.items()})
            merged.update(step_args.get(step.k, {}))
            active_values = {
                key: _normalize_runtime_value(meta.vars.get(key), value)
                for key, value in merged.items()
            }
            final_args = {}
            for field_key, value in active_values.items():
                field_def = meta.vars.get(field_key)
                if field_def is None:
                    final_args[field_key] = value
                    continue
                task_arg = task_args.get(field_key)
                condition = None if isinstance(task_arg, str) or task_arg is None else task_arg.if_
                if not is_condition_active(condition, active_values):
                    continue
                inject_key = field_def.as_ or field_key
                final_args[inject_key] = value
            steps.append(
                {
                    "key": step.k,
                    "task": task.k,
                    "fn": task.fn,
                    "enabled": bool(enabled),
                    "args": final_args,
                    "successBranches": [
                        branch.model_dump(by_alias=True, exclude_none=True)
                        for branch in step.successBranches
                    ],
                    "onSuccess": step.onSuccess,
                    "successGoto": step.successGoto,
                    "onFail": step.onFail,
                    "goto": step.goto,
                }
            )
        return {
            "flowKey": flow.k,
            "steps": steps,
            "globals": globals_values,
            "lockSteps": flow.lockSteps,
        }

    def build_runtime_script(self, meta: TemplateMeta, saved: TemplateSavedConfig, *, flow_key: str) -> str:
        runtime = self.build_runtime_payload(meta, saved, flow_key=flow_key)
        lines = [
            "local function __mlua_template_equal(left, right)",
            "  if type(left) ~= type(right) then return false end",
            "  if type(left) ~= 'table' then return left == right end",
            "  for key, value in pairs(left) do",
            "    if not __mlua_template_equal(value, right[key]) then return false end",
            "  end",
            "  for key, _ in pairs(right) do",
            "    if left[key] == nil then return false end",
            "  end",
            "  return true",
            "end",
            "local function __mlua_template_condition(value, operator, expected)",
            "  if operator == 'eq' then return __mlua_template_equal(value, expected) end",
            "  if operator == 'ne' then return not __mlua_template_equal(value, expected) end",
            "  if operator == 'in' then",
            "    for _, item in ipairs(expected or {}) do",
            "      if __mlua_template_equal(value, item) then return true end",
            "    end",
            "    return false",
            "  end",
            "  if type(value) ~= 'number' or type(expected) ~= 'number' then return false end",
            "  if operator == 'gt' then return value > expected end",
            "  if operator == 'gte' then return value >= expected end",
            "  if operator == 'lt' then return value < expected end",
            "  if operator == 'lte' then return value <= expected end",
            "  return false",
            "end",
            "local function __mlua_template_set_state(flow_key, step_key, task_key, step_index, status)",
            "  shared.set_key('template_state', {",
            "    flowKey = flow_key, stepKey = step_key, taskKey = task_key,",
            "    stepIndex = step_index, status = status",
            "  })",
            "end",
            f"shared.set_key('template_workflow_globals', {_python_to_lua_literal(runtime.get('globals') or {})})",
            f"__mlua_template_set_state({_python_to_lua_literal(runtime['flowKey'])}, nil, nil, 0, 'running')",
            f"log_info('[template] start workflow={runtime['flowKey']}')",
        ]
        step_indexes = {
            str(step.get("key") or f"step_{index}"): index
            for index, step in enumerate(runtime.get("steps", []), start=1)
        }
        for index, step in enumerate(runtime.get("steps", []), start=1):
            step_key = str(step.get("key") or f"step_{index}")
            fn_name = str(step.get("fn") or "")
            if not step.get("enabled", True):
                lines.append(f"::__mlua_template_step_{index}::")
                continue
            fn_ref_literal = _lua_global_ref_expr(fn_name)
            args_literal = _python_to_lua_literal(step.get("args") or {})
            # Both success and failure transitions target the final, user-ordered step sequence.
            fail_goto_index = step_indexes.get(str(step.get("goto") or ""))
            success_goto_index = step_indexes.get(str(step.get("successGoto") or ""))
            lines.extend(
                [
                    f"::__mlua_template_step_{index}::",
                    "do",
                    f"__mlua_template_set_state({_python_to_lua_literal(runtime['flowKey'])}, {_python_to_lua_literal(step_key)}, {_python_to_lua_literal(step.get('task') or '')}, {index}, 'running')",
                    f"local __mlua_template_args_{index} = {args_literal}",
                    f"log_info('[template] start step={step_key} fn={fn_name}')",
                    f"local __mlua_template_fn_{index} = {fn_ref_literal}",
                    f"if type(__mlua_template_fn_{index}) ~= 'function' then",
                    f"  error('template function not found: {fn_name}')",
                    "end",
                    f"local __mlua_template_ok_{index}, __mlua_template_result_{index} = pcall(__mlua_template_fn_{index}, __mlua_template_args_{index})",
                    f"if not __mlua_template_ok_{index} then",
                    f"  __mlua_template_set_state({_python_to_lua_literal(runtime['flowKey'])}, {_python_to_lua_literal(step_key)}, {_python_to_lua_literal(step.get('task') or '')}, {index}, 'failed')",
                    f"  log_error('[template] step failed: {step_key} => ' .. tostring(__mlua_template_result_{index}))",
                    f"  print('[template] step failed: {step_key} => ' .. tostring(__mlua_template_result_{index}))",
                    "  if 'continue' == " + _python_to_lua_literal(step.get("onFail") or "stop") + " then",
                    "    -- Continue with the next workflow step.",
                    *(
                        [
                            "  elseif 'goto' == " + _python_to_lua_literal(step.get("onFail") or "stop") + " then",
                            f"    goto __mlua_template_step_{fail_goto_index}",
                        ]
                        if fail_goto_index is not None
                        else []
                    ),
                    "  else",
                    f"    error(__mlua_template_result_{index})",
                    "  end",
                    "else",
                    f"  log_info('[template] finish step={step_key}')",
                    *[
                        line
                        for branch in step.get("successBranches", [])
                        for line in _build_lua_success_branch(branch, step_indexes)
                    ],
                    *(
                        [
                            "  if 'goto' == " + _python_to_lua_literal(step.get("onSuccess") or "continue") + " then",
                            f"    goto __mlua_template_step_{success_goto_index}",
                            "  elseif 'exit' == " + _python_to_lua_literal(step.get("onSuccess") or "continue") + " then",
                            f"    __mlua_template_set_state({_python_to_lua_literal(runtime['flowKey'])}, {_python_to_lua_literal(step_key)}, {_python_to_lua_literal(step.get('task') or '')}, {index}, 'success')",
                            "    return true",
                            "  end",
                        ]
                        if success_goto_index is not None
                        else [
                            "  if 'exit' == " + _python_to_lua_literal(step.get("onSuccess") or "continue") + " then",
                            f"    __mlua_template_set_state({_python_to_lua_literal(runtime['flowKey'])}, {_python_to_lua_literal(step_key)}, {_python_to_lua_literal(step.get('task') or '')}, {index}, 'success')",
                            "    return true",
                            "  end",
                        ]
                    ),
                    "end",
                    "end",
                ]
            )
        lines.append(
            f"__mlua_template_set_state({_python_to_lua_literal(runtime['flowKey'])}, nil, nil, 0, 'success')"
        )
        lines.append("return true")
        return "\n".join(lines)


def _build_lua_success_branch(branch: dict[str, Any], step_indexes: dict[str, int]) -> list[str]:
    """Build one ordered runtime branch against the mutable workflow globals table."""
    condition = branch.get("if") if isinstance(branch.get("if"), dict) else {}
    target_index = step_indexes.get(str(branch.get("goto") or ""))
    condition_key = str(condition.get("k") or "")
    if target_index is None or not condition_key:
        return []

    operator = ""
    expected: Any = None
    if isinstance(condition.get("in"), list) and condition["in"]:
        operator = "in"
        expected = condition["in"]
    else:
        for candidate in ("gt", "gte", "lt", "lte", "ne", "eq"):
            if candidate in condition:
                operator = candidate
                expected = condition[candidate]
                break
    if not operator:
        return []

    value_expr = (
        f"(shared.get_key('template_workflow_globals') or {{}})"
        f"[{_python_to_lua_literal(condition_key)}]"
    )
    return [
        f"  if __mlua_template_condition({value_expr}, {_python_to_lua_literal(operator)}, {_python_to_lua_literal(expected)}) then",
        f"    goto __mlua_template_step_{target_index}",
        "  end",
    ]


def _resolve_template_binding(value: Any, template_values: dict[str, Any]) -> Any:
    """Resolve editor binding descriptors while preserving legacy literal values."""
    if not isinstance(value, dict) or "$bind" not in value:
        return value
    source = value.get("$bind")
    if source == "literal":
        return value.get("value")
    if source == "var":
        return template_values.get(str(value.get("key") or ""))
    return value


def _normalize_runtime_value(field_def: Any, value: Any) -> Any:
    """Normalize values that use an encoded editor representation."""
    if field_def is None or field_def.tp != "json" or not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Preserve the source value so existing validation/error reporting paths
        # can identify the offending input without silently changing its content.
        return value


def _python_to_lua_literal(value: Any) -> str:
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t").replace("\"", "\\\"")
        return f'"{escaped}"'
    if isinstance(value, (list, tuple)):
        inner = ", ".join(_python_to_lua_literal(item) for item in value)
        return "{ " + inner + " }"
    if isinstance(value, dict):
        items = []
        for key, item in value.items():
            key_text = str(key)
            if _is_safe_lua_identifier(key_text):
                key_literal = key_text
            else:
                key_literal = f"[{_python_to_lua_literal(key_text)}]"
            items.append(f"{key_literal} = {_python_to_lua_literal(item)}")
        return "{ " + ", ".join(items) + " }"
    return _python_to_lua_literal(str(value))


_LUA_IDENTIFIER_ASCII_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _is_safe_lua_identifier(value: str) -> bool:
    return bool(_LUA_IDENTIFIER_ASCII_RE.fullmatch(value)) and not keyword.iskeyword(value)


def _blockly_lua_name(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if _is_safe_lua_identifier(text):
        return text
    encoded = text.encode("utf-8").hex("_").upper()
    return f"_{encoded}"


def _lua_global_ref_expr(path: str) -> str:
    parts = [part for part in str(path).split(".") if part]
    if not parts:
        return "nil"
    expr = "_G"
    for part in parts:
        normalized_part = _blockly_lua_name(part)
        expr += f"[{_python_to_lua_literal(normalized_part)}]"
    return expr


_global_template_store = TemplateStore()


def get_template_store() -> TemplateStore:
    return _global_template_store
