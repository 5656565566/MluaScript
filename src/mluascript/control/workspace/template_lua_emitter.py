from __future__ import annotations

import re
from typing import Any

from .template_runtime import RuntimeBranch, RuntimeFlow, RuntimeStep


class LuaWorkflowEmitter:
    """将强类型运行时任务流生成为可执行 Lua 源码"""

    def emit(self, flow: RuntimeFlow) -> str:
        lines = self._emit_prelude(flow)
        step_indexes = {
            step.key or f"step_{index}": index
            for index, step in enumerate(flow.steps, start=1)
        }
        for index, step in enumerate(flow.steps, start=1):
            lines.extend(self._emit_step(flow, step, index, step_indexes))
        lines.append(self._state_line(flow.key, None, 0, "success"))
        lines.append("return true")
        return "\n".join(lines)

    @staticmethod
    def _emit_prelude(flow: RuntimeFlow) -> list[str]:
        return [
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
            f"shared.set_key('template_workflow_globals', {_python_to_lua_literal(flow.globals)})",
            LuaWorkflowEmitter._state_line(flow.key, None, 0, "running"),
            f"log_info('[template] start workflow={flow.key}')",
        ]

    def _emit_step(
        self,
        flow: RuntimeFlow,
        step: RuntimeStep,
        index: int,
        step_indexes: dict[str, int],
    ) -> list[str]:
        step_key = step.key or f"step_{index}"
        if not step.enabled:
            return [f"::__mlua_template_step_{index}::"]

        function_reference = _lua_global_ref_expr(step.function_name)
        arguments_literal = _python_to_lua_literal(step.arguments)
        # 无论成功还是失败 状态转换都会指向最终由用户指定顺序的步骤序列
        failure_target_index = step_indexes.get(step.on_failure.target_step_key)
        success_target_index = step_indexes.get(step.on_success.target_step_key)

        lines = [
            f"::__mlua_template_step_{index}::",
            "do",
            self._state_line(flow.key, step, index, "running"),
            f"local __mlua_template_args_{index} = {arguments_literal}",
            f"log_info('[template] start step={step_key} fn={step.function_name}')",
            f"local __mlua_template_fn_{index} = {function_reference}",
            f"if type(__mlua_template_fn_{index}) ~= 'function' then",
            f"  error('template function not found: {step.function_name}')",
            "end",
            f"local __mlua_template_ok_{index}, __mlua_template_result_{index} = pcall(__mlua_template_fn_{index}, __mlua_template_args_{index})",
            f"if not __mlua_template_ok_{index} then",
            self._state_line(flow.key, step, index, "failed", indent="  "),
            f"  log_error('[template] step failed: {step_key} => ' .. tostring(__mlua_template_result_{index}))",
            f"  print('[template] step failed: {step_key} => ' .. tostring(__mlua_template_result_{index}))",
        ]
        lines.extend(self._emit_failure_transition(step, index, failure_target_index))
        lines.append("else")
        lines.append(f"  log_info('[template] finish step={step_key}')")
        for branch in step.success_branches:
            lines.extend(self._emit_success_branch(branch, step_indexes))
        lines.extend(self._emit_success_transition(flow, step, index, success_target_index))
        lines.extend(["end", "end"])
        return lines

    @staticmethod
    def _emit_failure_transition(
        step: RuntimeStep,
        index: int,
        target_index: int | None,
    ) -> list[str]:
        action_literal = _python_to_lua_literal(step.on_failure.action or "stop")
        lines = [
            "  if 'continue' == " + action_literal + " then",
            "    -- Continue with the next workflow step.",
        ]
        if target_index is not None:
            lines.extend(
                [
                    "  elseif 'goto' == " + action_literal + " then",
                    f"    goto __mlua_template_step_{target_index}",
                ]
            )
        lines.extend(
            [
                "  else",
                f"    error(__mlua_template_result_{index})",
                "  end",
            ]
        )
        return lines

    @staticmethod
    def _emit_success_branch(branch: RuntimeBranch, step_indexes: dict[str, int]) -> list[str]:
        target_index = step_indexes.get(branch.target_step_key)
        selected_operator = branch.condition.selected_operator()
        if target_index is None or not branch.condition.key or selected_operator is None:
            return []

        operator, expected = selected_operator
        value_expression = (
            f"(shared.get_key('template_workflow_globals') or {{}})"
            f"[{_python_to_lua_literal(branch.condition.key)}]"
        )
        return [
            f"  if __mlua_template_condition({value_expression}, {_python_to_lua_literal(operator)}, {_python_to_lua_literal(expected)}) then",
            f"    goto __mlua_template_step_{target_index}",
            "  end",
        ]

    @staticmethod
    def _emit_success_transition(
        flow: RuntimeFlow,
        step: RuntimeStep,
        index: int,
        target_index: int | None,
    ) -> list[str]:
        action_literal = _python_to_lua_literal(step.on_success.action or "continue")
        if target_index is not None:
            return [
                "  if 'goto' == " + action_literal + " then",
                f"    goto __mlua_template_step_{target_index}",
                "  elseif 'exit' == " + action_literal + " then",
                LuaWorkflowEmitter._state_line(flow.key, step, index, "success", indent="    "),
                "    return true",
                "  end",
            ]
        return [
            "  if 'exit' == " + action_literal + " then",
            LuaWorkflowEmitter._state_line(flow.key, step, index, "success", indent="    "),
            "    return true",
            "  end",
        ]

    @staticmethod
    def _state_line(
        flow_key: str,
        step: RuntimeStep | None,
        step_index: int,
        status: str,
        *,
        indent: str = "",
    ) -> str:
        step_key = None if step is None else step.key
        task_key = None if step is None else step.task_key
        return (
            f"{indent}__mlua_template_set_state("
            f"{_python_to_lua_literal(flow_key)}, "
            f"{_python_to_lua_literal(step_key)}, "
            f"{_python_to_lua_literal(task_key)}, "
            f"{step_index}, '{status}')"
        )


def _python_to_lua_literal(value: Any) -> str:
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t").replace('"', '\\"')
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
_LUA_RESERVED_WORDS = frozenset(
    {
        "and",
        "break",
        "do",
        "else",
        "elseif",
        "end",
        "false",
        "for",
        "function",
        "goto",
        "if",
        "in",
        "local",
        "nil",
        "not",
        "or",
        "repeat",
        "return",
        "then",
        "true",
        "until",
        "while",
    }
)


def _is_safe_lua_identifier(value: str) -> bool:
    return bool(_LUA_IDENTIFIER_ASCII_RE.fullmatch(value)) and value not in _LUA_RESERVED_WORDS


def _blockly_lua_name(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    # 全局函数通过字符串键访问 只需保持 Blockly 对 ASCII 名称的现有映射
    if _LUA_IDENTIFIER_ASCII_RE.fullmatch(text):
        return text
    encoded = text.encode("utf-8").hex("_").upper()
    return f"_{encoded}"


def _lua_global_ref_expr(path: str) -> str:
    parts = [part for part in str(path).split(".") if part]
    if not parts:
        return "nil"
    expression = "_G"
    for part in parts:
        normalized_part = _blockly_lua_name(part)
        expression += f"[{_python_to_lua_literal(normalized_part)}]"
    return expression
