from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .manager import WorkspaceManager, get_workspace_manager
from .template_lua_emitter import LuaWorkflowEmitter
from .template_models import TemplateMeta, TemplateSavedConfig
from .template_parser import parse_template_meta
from .template_runtime import RuntimeFlowBuilder


class TemplateStore:
    """模板元数据读取、用户配置持久化与运行时构建入口"""

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

    def build_runtime_payload(
        self,
        meta: TemplateMeta,
        saved: TemplateSavedConfig,
        *,
        flow_key: str,
    ) -> dict[str, Any]:
        """构建与现有调用方兼容的运行时字典"""
        runtime_flow = RuntimeFlowBuilder(meta, saved).build(flow_key=flow_key)
        return runtime_flow.to_payload()

    def build_runtime_script(self, meta: TemplateMeta, saved: TemplateSavedConfig, *, flow_key: str) -> str:
        """构建可直接交给运行时执行的 Lua 任务流源码"""
        runtime_flow = RuntimeFlowBuilder(meta, saved).build(flow_key=flow_key)
        return LuaWorkflowEmitter().emit(runtime_flow)


_global_template_store = TemplateStore()


def get_template_store() -> TemplateStore:
    return _global_template_store
