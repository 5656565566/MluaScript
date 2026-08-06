"""静态提取可打包项目中可供 Blockly 快捷调用的模块导出。"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .module_paths import blockly_source_to_module_key, script_path_to_module_key


def _blockly_exports(source: str) -> list[dict[str, object]]:
    root = ET.fromstring(source)
    procedures: dict[str, dict[str, object]] = {}
    exported_names: list[str] = []
    local_name = lambda element: element.tag.rsplit("}", 1)[-1]
    for block in (element for element in root.iter() if local_name(element) == "block"):
        block_type = block.attrib.get("type", "")
        children = list(block)
        fields = {
            field.attrib.get("name", ""): (field.text or "").strip()
            for field in children
            if local_name(field) == "field"
        }
        if block_type in {"procedures_defreturn", "procedures_defnoreturn"}:
            name = fields.get("NAME", "")
            mutation = next((child for child in children if local_name(child) == "mutation"), None)
            mutation_children = list(mutation) if mutation is not None else []
            params = [
                arg.attrib.get("name", "").strip()
                for arg in mutation_children
                if local_name(arg) == "arg"
            ]
            if name:
                procedures[name] = {
                    "name": name,
                    "params": [item for item in params if item],
                    "hasReturn": block_type == "procedures_defreturn",
                    "returnKind": "value" if block_type == "procedures_defreturn" else "none",
                    "callStyle": "function",
                }
        elif block_type == "lua_module_export_function":
            try:
                values = json.loads(fields.get("FUNC_VALUES", "[]"))
            except json.JSONDecodeError:
                values = []
            if isinstance(values, list):
                exported_names.extend(str(item).strip() for item in values if str(item).strip())
    return [procedures[name] for name in dict.fromkeys(exported_names) if name in procedures]


def _lua_function_signatures(source: str) -> dict[str, dict[str, object]]:
    """保守分析常见 Lua 函数声明；复杂控制流的返回状态标记为未知。"""

    patterns = (
        re.compile(r"(?:local\s+)?function\s+([A-Za-z_][\w]*)\s*\(([^)]*)\)(.*?)\bend\b", re.DOTALL),
        re.compile(r"(?:local\s+)?([A-Za-z_][\w]*)\s*=\s*function\s*\(([^)]*)\)(.*?)\bend\b", re.DOTALL),
    )
    signatures: dict[str, dict[str, object]] = {}
    for pattern in patterns:
        for match in pattern.finditer(source):
            name, raw_params, body = match.groups()
            params = [item.strip() for item in raw_params.split(",") if item.strip()]
            has_return, return_kind = _lua_return_shape(body)
            signatures[name] = {
                "params": params,
                "hasReturn": has_return,
                "returnKind": return_kind,
                "callStyle": "function",
            }
    return signatures


def _lua_return_shape(body: str) -> tuple[bool | None, str]:
    body_without_comments = re.sub(r"--\[\[.*?]]|--[^\n]*", "", body, flags=re.DOTALL)
    returns_value = any(
        return_match.group(1).strip()
        for return_match in re.finditer(r"\breturn\b([^\n;]*)", body_without_comments)
    )
    has_nested_control = bool(re.search(r"\b(?:if|for|while|repeat|function|do)\b", body_without_comments))
    has_return: bool | None = True if returns_value else None if has_nested_control else False
    return has_return, "value" if has_return is True else "none" if has_return is False else "unknown"


def _lua_module_table_exports(source: str) -> list[dict[str, object]]:
    """分析 ``local M = {}; function M.fn(); return M`` 风格模块。"""

    returned_tables = list(re.finditer(r"\breturn\s+([A-Za-z_][\w]*)\s*(?:--[^\n]*)?(?:$|\n)", source, re.MULTILINE))
    if not returned_tables:
        return []
    table_name = returned_tables[-1].group(1)
    if not re.search(rf"\blocal\s+{re.escape(table_name)}\s*=\s*{{\s*}}", source):
        return []

    exports: list[dict[str, object]] = []
    declaration_pattern = re.compile(
        rf"\bfunction\s+{re.escape(table_name)}([.:])([A-Za-z_][\w]*)\s*\(([^)]*)\)(.*?)\bend\b",
        re.DOTALL,
    )
    assignment_pattern = re.compile(
        rf"\b{re.escape(table_name)}\.([A-Za-z_][\w]*)\s*=\s*function\s*\(([^)]*)\)(.*?)\bend\b",
        re.DOTALL,
    )
    for match in declaration_pattern.finditer(source):
        separator, name, raw_params, body = match.groups()
        has_return, return_kind = _lua_return_shape(body)
        exports.append({
            "name": name,
            "params": [item.strip() for item in raw_params.split(",") if item.strip()],
            "hasReturn": has_return,
            "returnKind": return_kind,
            "callStyle": "method" if separator == ":" else "function",
        })
    for match in assignment_pattern.finditer(source):
        name, raw_params, body = match.groups()
        has_return, return_kind = _lua_return_shape(body)
        exports.append({
            "name": name,
            "params": [item.strip() for item in raw_params.split(",") if item.strip()],
            "hasReturn": has_return,
            "returnKind": return_kind,
            "callStyle": "function",
        })
    return list({str(item["name"]): item for item in exports}.values())


def _lua_exports(source: str) -> list[dict[str, object]]:
    module_table_exports = _lua_module_table_exports(source)
    if module_table_exports:
        return module_table_exports
    signatures = _lua_function_signatures(source)
    return_tables = list(re.finditer(r"\breturn\s*{(?P<body>.*?)}", source, re.DOTALL))
    if not return_tables:
        return []
    body = return_tables[-1].group("body")
    exports: list[dict[str, object]] = []
    export_pairs = list(re.finditer(r"([A-Za-z_][\w]*)\s*=\s*([A-Za-z_][\w]*)", body))
    assigned_spans = [match.span() for match in export_pairs]
    candidates = [(match.group(1), match.group(2)) for match in export_pairs]
    # 同时支持 `return { greet }` 这种键名与函数名相同的标准表写法。
    for match in re.finditer(r"(?:^|,)\s*([A-Za-z_][\w]*)\s*(?=,|$)", body):
        if not any(start <= match.start(1) < end for start, end in assigned_spans):
            candidates.append((match.group(1), match.group(1)))
    for export_name, function_name in candidates:
        if function_name not in signatures:
            continue
        signature = signatures[function_name]
        exports.append({"name": export_name, **signature})
    return exports


def build_project_module_index(project_root: Path, project_type: str) -> list[dict[str, object]]:
    """返回以相对路径为标识的静态模块导出索引。"""

    modules: list[dict[str, object]] = []
    if project_type == "blockly-package":
        for path in sorted((project_root / "blockly").rglob("*.xml")):
            relative = path.relative_to(project_root).as_posix()
            try:
                exports = _blockly_exports(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, ET.ParseError):
                exports = []
            modules.append({"key": blockly_source_to_module_key(relative), "source": relative, "kind": "blockly", "exports": exports})
    for path in sorted((project_root / "scripts").rglob("*.lua")) if (project_root / "scripts").is_dir() else []:
        relative = path.relative_to(project_root).as_posix()
        try:
            exports = _lua_exports(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError):
            exports = []
        modules.append({"key": script_path_to_module_key(relative), "source": relative, "kind": "lua", "exports": exports})
    return sorted(modules, key=lambda item: str(item["key"]).casefold())


def validate_blockly_module_references(project_root: Path) -> list[tuple[str, str]]:
    """返回 ``(source_path, message)`` 形式的失效模块引用。"""

    modules = build_project_module_index(project_root, "blockly-package")
    exports_by_module = {
        str(module["key"]): {str(item["name"]): item for item in module.get("exports", [])}
        for module in modules
    }
    diagnostics: list[tuple[str, str]] = []
    for path in sorted((project_root / "blockly").rglob("*.xml")):
        relative = path.relative_to(project_root).as_posix()
        try:
            root = ET.fromstring(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ET.ParseError):
            continue
        local_name = lambda element: element.tag.rsplit("}", 1)[-1]
        for block in (element for element in root.iter() if local_name(element) == "block"):
            block_type = block.attrib.get("type", "")
            if block_type not in {
                "lua_require_module_stmt",
                "lua_require_module_expr",
                "lua_project_module_call_stmt",
                "lua_project_module_call_expr",
            }:
                continue
            fields = {
                field.attrib.get("name", ""): (field.text or "").strip()
                for field in list(block)
                if local_name(field) == "field"
            }
            module_key = fields.get("MODULE_VALUE", "")
            if not module_key:
                continue
            if module_key not in exports_by_module:
                diagnostics.append((relative, f"引用的项目模块不存在: {module_key}"))
                continue
            if block_type.startswith("lua_project_module_call_"):
                function_name = fields.get("FUNCTION_VALUE", "")
                if function_name and function_name not in exports_by_module[module_key]:
                    diagnostics.append((relative, f"模块 {module_key} 不再导出函数: {function_name}"))
                    continue
                exported = exports_by_module[module_key].get(function_name)
                if not exported:
                    continue
                try:
                    saved_params = json.loads(fields.get("PARAM_VALUES", "[]"))
                except json.JSONDecodeError:
                    saved_params = []
                current_params = exported.get("params", [])
                if saved_params != current_params:
                    diagnostics.append(
                        (relative, f"模块 {module_key} 的函数 {function_name} 参数已变化，请重新选择该函数")
                    )
                saved_call_style = fields.get("CALL_STYLE", "function")
                current_call_style = exported.get("callStyle", "function")
                if saved_call_style != current_call_style:
                    diagnostics.append(
                        (relative, f"模块 {module_key} 的函数 {function_name} 调用方式已变化，请重新选择该函数")
                    )
                if block_type == "lua_project_module_call_expr" and exported.get("hasReturn") is False:
                    diagnostics.append((relative, f"模块 {module_key} 的函数 {function_name} 没有返回值，不能作为值调用"))
    return diagnostics
