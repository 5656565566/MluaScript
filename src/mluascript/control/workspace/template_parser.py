from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .template_models import TemplateMeta
from .template_normalizer import TemplateNormalizeError, normalize_template_meta

_TEMPLATE_START = "-- @mlua-template:start"
_TEMPLATE_END = "-- @mlua-template:end"


class TemplateParseError(ValueError):
    """模板解析异常。"""


@dataclass(slots=True)
class TemplateSource:
    script_path: str = ""
    start_line: int = 0
    end_line: int = 0
    raw_json: str = ""
    raw_meta: dict[str, Any] | None = None
    meta: TemplateMeta | None = None


def extract_template_block(script_text: str) -> TemplateSource | None:
    """从 Lua 脚本中提取模板注释块。"""
    lines = script_text.splitlines()
    start_idx = -1
    end_idx = -1
    for idx, line in enumerate(lines):
        if line.strip() == _TEMPLATE_START:
            start_idx = idx
            break
    if start_idx == -1:
        return None
    for idx in range(start_idx + 1, len(lines)):
        if lines[idx].strip() == _TEMPLATE_END:
            end_idx = idx
            break
    if end_idx == -1:
        raise TemplateParseError("模板注释缺少结束标记")

    json_lines: list[str] = []
    for raw_line in lines[start_idx + 1 : end_idx]:
        stripped = raw_line.lstrip()
        if stripped.startswith("--"):
            stripped = stripped[2:]
            if stripped.startswith(" "):
                stripped = stripped[1:]
        json_lines.append(stripped)
    raw_json = "\n".join(json_lines).strip()
    if not raw_json:
        raise TemplateParseError("模板注释内容为空")

    return TemplateSource(
        start_line=start_idx + 1,
        end_line=end_idx + 1,
        raw_json=raw_json,
    )


def parse_template_meta(script_text: str, *, script_path: str = "") -> TemplateSource | None:
    """从脚本中提取并标准化模板元数据。"""
    source = extract_template_block(script_text)
    if source is None:
        return None
    source.script_path = script_path
    try:
        raw_meta = json.loads(source.raw_json)
    except json.JSONDecodeError as exc:
        raise TemplateParseError(f"模板 JSON 解析失败: {exc}") from exc
    if not isinstance(raw_meta, dict):
        raise TemplateParseError("模板 JSON 顶层必须是对象")

    try:
        meta = normalize_template_meta(raw_meta)
    except TemplateNormalizeError as exc:
        raise TemplateParseError(str(exc)) from exc

    source.raw_meta = raw_meta
    source.meta = meta
    return source


def load_template_meta_from_file(path: str | Path) -> TemplateSource | None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    return parse_template_meta(text, script_path=str(file).replace("\\", "/"))


def dump_template_block(meta: TemplateMeta | dict[str, Any], *, indent: int = 2) -> str:
    """将模板对象编码为 Lua 注释块。"""
    normalized = meta if isinstance(meta, TemplateMeta) else normalize_template_meta(meta)
    text = json.dumps(normalized.model_dump(by_alias=True, exclude_none=True), ensure_ascii=False, indent=indent)
    comment_lines = ["-- @mlua-template:start"]
    comment_lines.extend(f"-- {line}" if line else "--" for line in text.splitlines())
    comment_lines.append("-- @mlua-template:end")
    return "\n".join(comment_lines)


def replace_template_block(script_text: str, meta: TemplateMeta | dict[str, Any], *, indent: int = 2) -> str:
    """替换或插入脚本模板注释块。"""
    new_block = dump_template_block(meta, indent=indent)
    source = extract_template_block(script_text)
    if source is None:
        prefix = new_block.strip()
        body = script_text.lstrip("\ufeff")
        return f"{prefix}\n\n{body}" if body else f"{prefix}\n"

    lines = script_text.splitlines()
    before = lines[: source.start_line - 1]
    after = lines[source.end_line :]
    merged = before + new_block.splitlines() + after
    suffix = "\n" if script_text.endswith("\n") else ""
    return "\n".join(merged) + suffix
