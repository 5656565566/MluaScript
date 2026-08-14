from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .manager import WorkspaceManager, get_workspace_manager
from .template_lua_emitter import LuaWorkflowEmitter
from .template_models import (
    SavedFlowConfig,
    TemplateFlowDef,
    TemplateMeta,
    TemplateSavedConfig,
    TemplateStepDef,
)
from .template_parser import parse_template_meta
from .template_runtime import RuntimeFlowBuilder


MAX_TEMPLATE_README_BYTES = 512 * 1024


class TemplateStore:
    """模板元数据读取、用户配置持久化与运行时构建入口"""

    def __init__(self, workspace_manager: WorkspaceManager | None = None, *, config_dir: Path | None = None) -> None:
        self.workspace_manager = workspace_manager or get_workspace_manager()
        self.config_dir = config_dir.resolve() if config_dir is not None else None

    def get_template_meta(self, script_path: str) -> TemplateMeta | None:
        text = self.workspace_manager.read_script(script_path)
        return self.get_template_meta_from_source(text, script_path=script_path)

    @staticmethod
    def get_template_meta_from_source(text: str, *, script_path: str = "") -> TemplateMeta | None:
        """从内存脚本快照解析模板，供 Blockly 生成 Lua 和构建包入口复用。"""

        source = parse_template_meta(str(text or ""), script_path=script_path)
        return source.meta if source else None

    def get_readme(self, script_path: str) -> dict[str, str] | None:
        """读取模板脚本所属项目根目录的 README，不接受项目外路径。"""

        script_file = self.workspace_manager._resolve_workspace_path(script_path)
        project = self.workspace_manager.resolve_project_by_root(script_file.parent)
        readme_path = Path(project.root_dir) / "README.md"
        if not readme_path.is_file() or readme_path.is_symlink():
            return None
        raw = readme_path.read_bytes()
        if len(raw) > MAX_TEMPLATE_README_BYTES:
            raise ValueError("README.md 超过 512 KiB 限制")
        try:
            markdown = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("README.md 必须使用 UTF-8 编码") from exc
        return {"name": "README.md", "path": "README.md", "markdown": markdown}

    def get_saved_config_path(self, script_path: str) -> str:
        script_file = self.workspace_manager._resolve_workspace_path(script_path)
        config_dir = self.config_dir or (self.workspace_manager.root_dir / "config")
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

    def build_task_runtime_script(self, meta: TemplateMeta, saved: TemplateSavedConfig, *, task_key: str) -> str:
        """把单任务模板转换为只有一个步骤的运行流，复用统一参数归一化和执行器。"""

        task = next((item for item in meta.tasks if item.k == task_key), None)
        if task is None:
            raise KeyError(task_key)
        flow_key = f"__task__{task_key}"
        step_key = f"__step__{task_key}"
        synthetic_meta = meta.model_copy(deep=True)
        synthetic_meta.flows = [
            TemplateFlowDef(
                k=flow_key,
                t=task.t or task.k,
                steps=[TemplateStepDef(k=step_key, task=task.k, onSuccess="exit")],
            )
        ]
        synthetic_saved = saved.model_copy(deep=True)
        task_config = saved.tasks.get(task_key)
        synthetic_saved.flows[flow_key] = SavedFlowConfig(
            stepArgs={step_key: dict(task_config.params if task_config else {})},
        )
        runtime_flow = RuntimeFlowBuilder(synthetic_meta, synthetic_saved).build(flow_key=flow_key)
        return LuaWorkflowEmitter().emit(runtime_flow)


_global_template_store = TemplateStore()


def get_template_store() -> TemplateStore:
    return _global_template_store
