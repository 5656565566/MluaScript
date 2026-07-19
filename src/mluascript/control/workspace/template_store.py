from __future__ import annotations

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
        globals_values = dict(saved_flow.globals if saved_flow else {})
        step_enabled = dict(saved_flow.stepEnabled if saved_flow else {})
        step_args = dict(saved_flow.stepArgs if saved_flow else {})
        step_order = list(saved_flow.stepOrder if saved_flow and saved_flow.stepOrder else [step.k for step in flow.steps])
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
            enabled = step_enabled.get(step.k, step.enabled)
            merged = {}
            for field_key in task.args:
                field_def = meta.vars.get(field_key)
                if field_def is None:
                    continue
                merged[field_key] = field_def.def_
            merged.update({key: _resolve_template_binding(value, template_values) for key, value in task.defaults.items()})
            merged.update({key: value for key, value in globals_values.items() if key in task.args})
            merged.update({key: _resolve_template_binding(value, template_values) for key, value in step.args.items()})
            merged.update(step_args.get(step.k, {}))
            active_values = dict(merged)
            final_args = {}
            for field_key, value in merged.items():
                field_def = meta.vars.get(field_key)
                if field_def is None:
                    final_args[field_key] = value
                    continue
                if not is_condition_active(field_def.if_, active_values):
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
        }

    def build_runtime_script(self, meta: TemplateMeta, saved: TemplateSavedConfig, *, flow_key: str) -> str:
        runtime = self.build_runtime_payload(meta, saved, flow_key=flow_key)
        lines = [
            f"log_info('[template] start workflow={runtime['flowKey']}')",
        ]
        step_indexes = {
            str(step.get("key") or f"step_{index}"): index
            for index, step in enumerate(runtime.get("steps", []), start=1)
        }
        for index, step in enumerate(runtime.get("steps", []), start=1):
            step_key = str(step.get("key") or f"step_{index}")
            fn_name = str(step.get("fn") or "")
            fn_ref_literal = _lua_global_ref_expr(fn_name)
            args_literal = _python_to_lua_literal(step.get("args") or {})
            # Both success and failure transitions target the final, user-ordered step sequence.
            fail_goto_index = step_indexes.get(str(step.get("goto") or ""))
            success_goto_index = step_indexes.get(str(step.get("successGoto") or ""))
            lines.extend(
                [
                    f"::__mlua_template_step_{index}::",
                    "do",
                    f"local __mlua_template_args_{index} = {args_literal}",
                    f"log_info('[template] start step={step_key} fn={fn_name}')",
                    f"local __mlua_template_fn_{index} = {fn_ref_literal}",
                    f"if type(__mlua_template_fn_{index}) ~= 'function' then",
                    f"  error('template function not found: {fn_name}')",
                    "end",
                    f"local __mlua_template_ok_{index}, __mlua_template_result_{index} = pcall(__mlua_template_fn_{index}, __mlua_template_args_{index})",
                    f"if not __mlua_template_ok_{index} then",
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
                    *(
                        [
                            "  if 'goto' == " + _python_to_lua_literal(step.get("onSuccess") or "continue") + " then",
                            f"    goto __mlua_template_step_{success_goto_index}",
                            "  elseif 'exit' == " + _python_to_lua_literal(step.get("onSuccess") or "continue") + " then",
                            "    return true",
                            "  end",
                        ]
                        if success_goto_index is not None
                        else [
                            "  if 'exit' == " + _python_to_lua_literal(step.get("onSuccess") or "continue") + " then",
                            "    return true",
                            "  end",
                        ]
                    ),
                    "end",
                    "end",
                ]
            )
        lines.append("return true")
        return "\n".join(lines)


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
