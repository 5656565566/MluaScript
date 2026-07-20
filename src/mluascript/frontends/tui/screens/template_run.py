from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.timer import Timer
import uuid

from textual.widgets import Button, ContentSwitcher, Input, Static, Switch, TabbedContent, TabPane, Tabs, Tab

from mluascript.control.facade import get_control_facade
from mluascript.control.state.models import TaskListItemView
from mluascript.control.workspace import SavedFlowConfig, TemplateCondition, TemplateSavedConfig, TemplateVarDef, get_template_store, is_condition_active


@dataclass(frozen=True, slots=True)
class _TemplateFieldRow:
    field: TemplateVarDef
    depth: int
    active: bool


def _task_arg_key(arg: Any) -> str:
    return arg if isinstance(arg, str) else str(getattr(arg, "k", "") or "")


def _build_task_field_rows(
    args: list[Any],
    vars_by_key: dict[str, TemplateVarDef],
    values: dict[str, Any],
) -> list[_TemplateFieldRow]:
    nodes: list[tuple[TemplateVarDef, TemplateCondition | None]] = []
    for arg in args:
        key = _task_arg_key(arg)
        field = vars_by_key.get(key)
        if field is None:
            continue
        condition = None if isinstance(arg, str) else getattr(arg, "if_", None)
        nodes.append((field, condition))

    node_by_key = {field.k: index for index, (field, _) in enumerate(nodes)}
    children: dict[int, list[int]] = {index: [] for index in range(len(nodes))}
    roots: list[int] = []
    for index, (_, condition) in enumerate(nodes):
        parent_index = node_by_key.get(condition.k) if condition is not None and condition.k else None
        if parent_index is not None and parent_index != index:
            children[parent_index].append(index)
        else:
            roots.append(index)

    rows: list[_TemplateFieldRow] = []
    visited: set[int] = set()

    def visit(index: int, depth: int, parent_active: bool) -> None:
        if index in visited:
            return
        visited.add(index)
        field, condition = nodes[index]
        active = parent_active and is_condition_active(condition, values)
        rows.append(_TemplateFieldRow(field=field, depth=depth, active=active))
        for child_index in children[index]:
            visit(child_index, depth + 1, active)

    for root_index in roots:
        visit(root_index, 0, True)
    # 无效循环关系不应让 TUI 崩溃，按声明顺序将其作为独立根节点展示。
    for index in range(len(nodes)):
        if index not in visited:
            visit(index, 0, True)
    return rows


class TemplateRunScreen(Container):
    DEFAULT_CSS = """
    TemplateRunScreen {
        width: 100%;
        height: 1fr;
        overflow: hidden;
    }

    .tab-scroll-area {
        height: 1fr;
        padding: 0 1;
        overflow-y: auto;
    }

    .section-title {
        margin: 1 0 0 0;
        text-style: bold;
    }

    .section-desc {
        margin: 0 0 1 0;
        color: $text-muted;
    }

    .workflow-list,
    .step-list,
    .task-log-list,
    .meta-list {
        height: auto;
        width: 100%;
    }

    .step-list-row {
        height: 3;
        width: 100%;
        margin: 0 0 1 0;
    }

    .step-list-btn {
        margin: 0 !important;
        width: 1fr !important;
    }

    .list-move-btn {
        width: 4 !important;
        min-width: 4 !important;
        margin: 0 0 0 1 !important;
    }

    .list-item {
        margin: 0 0 1 0;
        width: 100%;
    }

    .list-item.-active {
        background: #1E88E5 !important;
        color: white !important;
        text-style: bold;
    }

    .workflow-header,
    .detail-header,
    .footer-box {
        border: solid $panel;
        padding: 1;
        margin: 0 0 1 0;
    }

    .global-panel,
    .step-detail-panel,
    .step-list-panel,
    .workflow-list-panel,
    .task-list-panel {
        border: solid $panel;
        padding: 1;
        height: auto;
    }

    .shell-layout,
    .workflow-layout,
    .step-layout,
    .task-layout {
        height: auto;
        width: 100%;
    }

    .workflow-list-panel {
        width: 32;
        min-width: 24;
    }

    .step-list-panel,
    .task-list-panel {
        width: 40;
        min-width: 30;
    }

    .step-detail-panel {
        width: 1fr;
    }

    #template-step-fields,
    #template-globals {
        height: auto;
    }

    .field-row {
        margin: 0 0 1 0;
        height: auto;
    }

    .field-key {
        color: $text-muted;
    }

    .field-desc {
        color: $text-muted;
        margin: 0 0 1 0;
    }

    .field-input,
    .field-json-input {
        width: 100%;
        margin: 0 0 1 0;
    }

    .field-json-input {
        height: 6;
    }

    .field-switch-row {
        margin: 0 0 1 0;
        height: auto;
    }

    .field-switch-label {
        width: 1fr;
    }

    .task-action-row,
    .top-action-row,
    .workflow-action-row,
    .step-action-row {
        height: auto;
        width: 100%;
    }

    .small-btn {
        width: 12;
        margin-right: 1;
    }

    .run-btn {
        background: #2E7D32;
    }

    .muted-box {
        color: $text-muted;
        border: dashed $panel;
        padding: 1;
        margin: 0 0 1 0;
    }
    """

    BINDINGS = [
        Binding("enter", "run_selected_workflow", "执行工作流", tooltip="执行当前选中的模板工作流"),
    ]

    def __init__(self, name: str | None = None, id: str | None = None, classes: str | None = None) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._refresh_timer: Timer | None = None
        self._selected_script_path: str | None = None
        self._selected_workflow_key: str | None = None
        self._selected_step_key: str | None = None
        self._workflow_button_map: dict[str, str] = {}
        self._step_button_map: dict[str, str] = {}
        self._field_input_map: dict[str, tuple[str, str, str]] = {}
        self._field_switch_map: dict[str, tuple[str, str, str]] = {}
        self._workflow_buttons: dict[str, Button] = {}
        self._step_buttons: dict[str, Button] = {}
        self._field_widgets: dict[str, Any] = {}
        self._meta_widgets: dict[str, Static] = {}
        self._selected_script_meta: dict[str, Any] | None = None
        self._selected_saved_config: TemplateSavedConfig | None = None
        self._selected_config_path: str = ""
        self._rendered_detail_key: tuple[str | None, str | None, str | None] = (None, None, None)
        self._rendered_global_key: tuple[str | None, str | None] = (None, None)

    @property
    def _control(self):
        return get_control_facade()

    @property
    def _template_store(self):
        return get_template_store()

    def compose(self) -> ComposeResult:
        with TabbedContent(id="template-run-tabs"):
            with TabPane("模板配置", id="template-run-tab-config"):
                with ScrollableContainer(classes="tab-scroll-area"):
                    yield Static("模板运行", classes="section-title")
                    with Horizontal(classes="top-action-row"):
                        yield Button("执行工作流", id="btn-template-run", classes="run-btn")
                    yield Static("当前未选择模板任务", id="template-header", classes="workflow-header")
                    yield Static("请从运行任务页进入模板执行", id="template-description", classes="section-desc")
                    yield Vertical(id="template-globals", classes="global-panel")
                    yield Static("工作流", id="template-workflow-title", classes="section-title")
                    yield Tabs(id="template-workflow-tabs")
                    with ContentSwitcher(initial="template-workflow-empty", id="template-workflow-switcher"):
                        with Vertical(id="template-workflow-empty"):
                            yield Static("请先从运行任务页进入模板任务", classes="muted-box")
                        with Vertical(id="template-workflow-content", classes="step-layout"):
                            yield Static("任务列表", classes="section-title")
                            yield Static("点击任务跳转到配置页", classes="section-desc")
                            yield Vertical(id="template-step-list", classes="step-list")
            with TabPane("任务配置", id="template-run-tab-step"):
                with ScrollableContainer(classes="tab-scroll-area"):
                    yield Static("任务配置", classes="section-title")
                    yield Static("配置当前选中任务的详细参数、启用状态与执行顺序。", classes="section-desc")
                    with Vertical(classes="step-detail-panel"):
                        yield Static("当前未选择任务", id="step-header", classes="detail-header")
                        yield Static("暂无任务说明", id="step-description", classes="section-desc")
                        yield Vertical(id="template-step-fields")
            with TabPane("脚本信息", id="template-run-tab-meta"):
                with ScrollableContainer(classes="tab-scroll-area"):
                    yield Static("脚本信息", classes="section-title")
                    yield Vertical(id="template-meta-list", classes="meta-list")

    def on_mount(self) -> None:
        self._refresh_timer = self.set_interval(1.0, self._refresh_all)
        self._refresh_all()

    def _refresh_all(self) -> None:
        tasks = self._control.list_task_views()
        self._sync_selected_task(tasks)
        self._load_selected_template_state()
        self._render_workflow_tabs()
        self._render_template_summary()
        self._render_globals_panel()
        self._render_step_list()
        self._render_step_detail()
        self._render_meta_panel()

    def _sync_selected_template(self) -> None:
        if not self._selected_script_path:
            self._selected_workflow_key = None
            self._selected_step_key = None
            return
        
        if self._selected_script_meta and self._selected_script_meta.get("path") == self._selected_script_path:
            meta = self._selected_script_meta["meta"]
        else:
            try:
                meta = self._template_store.get_template_meta(self._selected_script_path)
                if meta is not None:
                    self._selected_script_meta = {"path": self._selected_script_path, "meta": meta}
                    self._selected_saved_config = self._template_store.load_saved_config(self._selected_script_path)
                    self._selected_config_path = self._template_store.get_saved_config_path(self._selected_script_path)
            except Exception:
                self._selected_script_path = None
                self._selected_workflow_key = None
                self._selected_step_key = None
                return

        if meta is None or not meta.flows:
            self._selected_workflow_key = None
            self._selected_step_key = None
            return
        available_keys = [flow.k for flow in meta.flows]
        if self._selected_workflow_key not in available_keys:
            self._selected_workflow_key = meta.entry.flow or (available_keys[0] if available_keys else None)
        current_flow = self._get_current_flow(meta)
        step_keys = [step.k for step in current_flow.steps] if current_flow is not None else []
        if self._selected_step_key not in step_keys:
            self._selected_step_key = step_keys[0] if step_keys else None

    def _sync_selected_task(self, tasks: list[TaskListItemView]) -> None:
        if not self._selected_script_path:
            template_tasks = self._filter_template_tasks(tasks)
            if template_tasks:
                selected = template_tasks[0]
                script_path = str(selected.summary.get("template_script_path") or selected.summary.get("script_path") or "")
                workflow_key = str(selected.summary.get("workflow_key") or "")
                if script_path:
                    self._selected_script_path = script_path
                if workflow_key:
                    self._selected_workflow_key = workflow_key
        self._sync_selected_template()

    def _load_selected_template_state(self) -> None:
        script_path = self._selected_script_path
        if not script_path:
            self._selected_script_meta = None
            self._selected_saved_config = None
            self._selected_config_path = ""
            return
        
        if self._selected_script_meta and self._selected_script_meta.get("path") == script_path and self._selected_saved_config is not None:
            meta = self._selected_script_meta["meta"]
            saved = self._selected_saved_config
        else:
            try:
                meta = self._template_store.get_template_meta(script_path)
                if meta is None:
                    self._selected_script_meta = None
                    self._selected_saved_config = None
                    self._selected_config_path = ""
                    return
                saved = self._template_store.load_saved_config(script_path)
                self._selected_script_meta = {
                    "path": script_path,
                    "meta": meta,
                }
                self._selected_saved_config = saved
                self._selected_config_path = self._template_store.get_saved_config_path(script_path)
            except Exception:
                self._selected_script_meta = None
                self._selected_saved_config = None
                self._selected_config_path = ""
                return

        if not self._selected_workflow_key:
            self._selected_workflow_key = saved.selectedFlowKey or meta.entry.flow or (meta.flows[0].k if meta.flows else None)
        current_flow = self._get_current_flow(meta)
        if current_flow is not None:
            ordered_steps = self._ordered_steps(current_flow)
            if ordered_steps and self._selected_step_key not in {step.k for step in ordered_steps}:
                self._selected_step_key = ordered_steps[0].k

    def _get_current_meta(self):
        return None if self._selected_script_meta is None else self._selected_script_meta["meta"]

    def _get_current_flow(self, meta=None):
        current_meta = meta or self._get_current_meta()
        if current_meta is None:
            return None
        return next((item for item in current_meta.flows if item.k == self._selected_workflow_key), None)

    def _get_saved_flow(self):
        if self._selected_saved_config is None or not self._selected_workflow_key:
            return None
        return self._selected_saved_config.flows.get(self._selected_workflow_key)

    def _ordered_steps(self, flow) -> list[Any]:
        saved_flow = self._get_saved_flow()
        order = list(saved_flow.stepOrder) if saved_flow and saved_flow.stepOrder else [step.k for step in flow.steps]
        order_map = {key: index for index, key in enumerate(order)}
        original_map = {step.k: index for index, step in enumerate(flow.steps)}
        return sorted(flow.steps, key=lambda item: order_map.get(item.k, len(order_map) + original_map.get(item.k, 0)))

    def _render_workflow_tabs(self) -> None:
        tabs = self.query_one("#template-workflow-tabs", Tabs)
        switcher = self.query_one("#template-workflow-switcher", ContentSwitcher)
        title_widget = self.query_one("#template-workflow-title", Static)
        meta = self._get_current_meta()
        
        if meta is None or not meta.flows:
            switcher.current = "template-workflow-empty"
            tabs.display = False
            title_widget.display = False
            tabs.clear()
            return
            
        if len(meta.flows) <= 1:
            tabs.display = False
            title_widget.display = False
            tabs.clear()
        else:
            tabs.display = True
            title_widget.display = True
            existing = {tab.id for tab in tabs.query(Tab) if tab.id}
            target_ids = {f"template-flow-pane-{index}" for index, _ in enumerate(meta.flows)}
            for tab in list(tabs.query(Tab)):
                if tab.id and tab.id not in target_ids:
                    tab.remove()
                    
            for index, flow in enumerate(meta.flows):
                tab_id = f"template-flow-pane-{index}"
                if tab_id not in existing:
                    tabs.add_tab(Tab(flow.ut or flow.t or flow.k or f"工作流 {index+1}", id=tab_id))
            active_tab = f"template-flow-pane-0"
            for index, flow in enumerate(meta.flows):
                if flow.k == self._selected_workflow_key:
                    active_tab = f"template-flow-pane-{index}"
                    break
            tabs.active = active_tab
            
        switcher.current = "template-workflow-content"

    def _render_template_summary(self) -> None:
        header = self.query_one("#template-header", Static)
        description = self.query_one("#template-description", Static)
        meta = self._get_current_meta()
        flow = self._get_current_flow()
        if meta is None:
            header.update("当前未选择模板任务")
            description.update("请从运行任务页进入模板执行")
            return
        title = meta.ut or meta.t or self._selected_script_path or "模板运行"
        if flow is not None:
            title = f"{title} / {flow.ut or flow.t or flow.k}"
        header.update(title)
        description.update((flow.ud or flow.d) if flow is not None and (flow.ud or flow.d) else (meta.ud or meta.d or "暂无模板描述"))

    def _render_globals_panel(self) -> None:
        container = self.query_one("#template-globals", Vertical)
        meta = self._get_current_meta()
        flow = self._get_current_flow()

        current_global_key = (self._selected_script_path, self._selected_workflow_key)
        needs_rebuild = not hasattr(self, "_rendered_global_key") or self._rendered_global_key != current_global_key

        if needs_rebuild:
            for k in list(self._field_input_map.keys()):
                if self._field_input_map[k][0] == "global":
                    self._field_input_map.pop(k, None)
            for k in list(self._field_switch_map.keys()):
                if self._field_switch_map[k][0] == "global":
                    self._field_switch_map.pop(k, None)
            for k in list(self._field_widgets.keys()):
                if "-global-" in k:
                    self._field_widgets.pop(k, None)
            for child in list(container.children):
                child.remove()
            self._global_rebuild_id = uuid.uuid4().hex
            self._rendered_global_key = current_global_key

        if meta is None or flow is None:
            if needs_rebuild:
                container.mount(Static("暂无全局变量", classes="muted-box"))
            return
            
        if not flow.g:
            if needs_rebuild:
                container.mount(Static("暂无全局变量", classes="muted-box"))
            return

        ordered_fields = [meta.vars[key] for key in flow.g if key in meta.vars]

        rebuild_id = getattr(self, "_global_rebuild_id", "")
        for field in ordered_fields:
            self._mount_field_editor(container, field=field, scope="global", owner_key="global", rebuild_id=rebuild_id)

    def _render_step_list(self) -> None:
        container = self.query_one("#template-step-list", Vertical)
        meta = self._get_current_meta()
        flow = self._get_current_flow()
        
        # We need a total rebuild of the list to ensure buttons render correctly
        for child in list(container.children):
            child.remove()
        self._step_buttons.clear()
        
        if meta is None or flow is None:
            container.mount(Static("请先选择工作流", classes="muted-box"))
            return
            
        ordered = self._ordered_steps(flow)
        self._step_button_map = {f"template-step-{index}": step.k for index, step in enumerate(ordered)}
        
        for index, step in enumerate(ordered):
            name = f"template-step-{index}"
            enabled_text = "启用" if self._is_step_enabled(step.k, step.enabled) else "禁用"
            task_def = next((item for item in meta.tasks if item.k == step.task), None)
            task_title = task_def.ut or task_def.t or task_def.k if task_def else step.task
            label = f"[{enabled_text}] {task_title}"
            
            button = Button(label, name=name, classes="list-item step-list-btn")
            self._step_buttons[name] = button
            if step.k == self._selected_step_key:
                button.add_class("-active")
                
            up_btn = Button("▲", id=f"step-list-up-{index}", classes="list-move-btn", disabled=step.allowReorder is False)
            down_btn = Button("▼", id=f"step-list-down-{index}", classes="list-move-btn", disabled=step.allowReorder is False)
            
            row = Horizontal(button, up_btn, down_btn, classes="step-list-row")
            container.mount(row)

    def _render_step_detail(self) -> None:
        header = self.query_one("#step-header", Static)
        description = self.query_one("#step-description", Static)
        container = self.query_one("#template-step-fields", Vertical)
        meta = self._get_current_meta()
        flow = self._get_current_flow()

        current_detail_key = (self._selected_script_path, self._selected_workflow_key, self._selected_step_key)
        needs_rebuild = not hasattr(self, "_rendered_detail_key") or self._rendered_detail_key != current_detail_key

        if needs_rebuild:
            for k in list(self._field_input_map.keys()):
                if self._field_input_map[k][0] == "step":
                    self._field_input_map.pop(k, None)
            for k in list(self._field_switch_map.keys()):
                if self._field_switch_map[k][0] in ("step", "step_enabled"):
                    self._field_switch_map.pop(k, None)
            for k in list(self._field_widgets.keys()):
                if "-step-" in k or k.startswith("step-enabled-"):
                    self._field_widgets.pop(k, None)
            for child in list(container.children):
                child.remove()
            self._step_rebuild_id = uuid.uuid4().hex
            self._rendered_detail_key = current_detail_key

        if meta is None or flow is None:
            header.update("当前未选择任务")
            description.update("暂无任务说明")
            if needs_rebuild:
                container.mount(Static("请先在 模板配置 中选择模板与工作流", classes="muted-box"))
            return
        step = next((item for item in self._ordered_steps(flow) if item.k == self._selected_step_key), None)
        if step is None:
            header.update("当前未选择任务")
            description.update("暂无任务说明")
            if needs_rebuild:
                container.mount(Static("请在 模板配置 的 任务列表 中选择一个任务", classes="muted-box"))
            return
            
        task_def = next((item for item in meta.tasks if item.k == step.task), None)
        task_title = task_def.ut or task_def.t or task_def.k if task_def else step.task
        task_desc = task_def.ud or task_def.d or "该任务没有额外说明" if task_def else "该任务没有额外说明"
        
        header.update(task_title)
        description.update(task_desc)

        rebuild_id = getattr(self, "_step_rebuild_id", "")
        suffix = f"-{rebuild_id}" if rebuild_id else ""
        switch_id = f"step-enabled-{step.k}{suffix}"
        is_enabled = self._is_step_enabled(step.k, step.enabled)

        if needs_rebuild:
            enabled_switch = Switch(value=is_enabled, id=switch_id)
            self._field_switch_map[switch_id] = ("step_enabled", step.k, "")
            container.mount(Horizontal(Static("启用该任务", classes="field-switch-label"), enabled_switch, classes="field-switch-row"))
            self._field_widgets[switch_id] = enabled_switch
        else:
            enabled_switch = self._field_widgets.get(switch_id)
            if isinstance(enabled_switch, Switch) and enabled_switch.value != is_enabled:
                with enabled_switch.prevent(Switch.Changed):
                    enabled_switch.value = is_enabled

        task_def = next((item for item in meta.tasks if item.k == step.task), None)
        if task_def is None:
            if needs_rebuild:
                container.mount(Static("该步骤引用的任务不存在", classes="muted-box"))
            return

        values = self._build_active_values(step.k)
        field_rows = _build_task_field_rows(task_def.args, meta.vars, values)
        if not field_rows:
            if needs_rebuild:
                container.mount(Static("该步骤未定义可配置字段", classes="muted-box"))
            return

        for row in field_rows:
            self._mount_field_editor(
                container,
                field=row.field,
                scope="step",
                owner_key=step.k,
                is_active=row.active,
                depth=row.depth,
                rebuild_id=rebuild_id,
            )

    def _render_meta_panel(self) -> None:
        container = self.query_one("#template-meta-list", Vertical)
        container.remove_children()
        meta = self._get_current_meta()
        script_path = self._selected_script_path
        if meta is None or not script_path:
            container.mount(Static("当前没有选中的模板脚本", classes="muted-box"))
            return
        items = [
            f"脚本: {Path(script_path).name}",
            f"路径: {script_path}",
            f"配置: {self._selected_config_path or '未生成'}",
            f"模板标题: {meta.ut or meta.t or '-'}",
            f"默认工作流: {meta.entry.flow or '-'}",
            f"当前工作流: {self._selected_workflow_key or '-'}",
        ]
        for text in items:
            container.mount(Static(text, classes="footer-box"))

    def _build_active_values(self, step_key: str) -> dict[str, Any]:
        values = dict(self._get_globals_values())
        meta = self._get_current_meta()
        flow = self._get_current_flow()
        if meta is None or flow is None:
            return values
        step = next((item for item in flow.steps if item.k == step_key), None)
        if step is None:
            return values
        task_def = next((item for item in meta.tasks if item.k == step.task), None)
        if task_def is None:
            return values
        for arg in task_def.args:
            field_key = _task_arg_key(arg)
            field = meta.vars.get(field_key)
            if field is None:
                continue
            values[field_key] = self._get_step_value(step_key, field)
        return values

    def _get_globals_values(self) -> dict[str, Any]:
        saved_flow = self._get_saved_flow()
        return dict(saved_flow.globals) if saved_flow is not None else {}

    def _get_global_value(self, key: str, field: TemplateVarDef) -> Any:
        globals_values = self._get_globals_values()
        if key in globals_values:
            return globals_values[key]
        return field.def_

    def _get_step_value(self, step_key: str, field: TemplateVarDef) -> Any:
        saved_flow = self._get_saved_flow()
        if saved_flow is not None:
            step_args = saved_flow.stepArgs.get(step_key, {})
            if field.k in step_args:
                return step_args[field.k]
        return field.def_

    def _is_step_enabled(self, step_key: str, default_enabled: bool) -> bool:
        saved_flow = self._get_saved_flow()
        if saved_flow is not None and step_key in saved_flow.stepEnabled:
            return bool(saved_flow.stepEnabled[step_key])
        return bool(default_enabled)

    def _mount_field_editor(self, container: Vertical, *, field: TemplateVarDef, scope: str, owner_key: str, is_active: bool = True, depth: int = 0, rebuild_id: str = "") -> None:
        label = f"{'  ' * depth}{field.t or field.k}"
        suffix = f"-{rebuild_id}" if rebuild_id else ""
        field_id = f"field-{scope}-{owner_key}-{field.k}{suffix}"
        title_id = f"field-title-{scope}-{owner_key}-{field.k}{suffix}"
        desc_id = f"field-desc-{scope}-{owner_key}-{field.k}{suffix}"

        self._mount_or_update_static(container, title_id, label, classes="section-title", display=is_active)
        if field.d:
            self._mount_or_update_static(container, desc_id, field.d, classes="field-desc", display=is_active)
        else:
            if desc_id in self._field_widgets:
                self._field_widgets[desc_id].display = False

        if field.tp == "bool":
            value = bool(self._get_global_value(field.k, field) if scope == "global" else self._get_step_value(owner_key, field))
            switch = self._field_widgets.get(field_id)
            row_id = f"row-{field_id}"
            if not isinstance(switch, Switch):
                switch = Switch(value=value, id=field_id)
                row = Horizontal(Static("开关", classes="field-switch-label"), switch, classes="field-switch-row", id=row_id)
                row.display = is_active
                container.mount(row)
                self._field_widgets[field_id] = switch
                self._field_widgets[row_id] = row
            else:
                if switch.value != value:
                    with switch.prevent(Switch.Changed):
                        switch.value = value
                if row_id in self._field_widgets:
                    self._field_widgets[row_id].display = is_active
            self._field_switch_map[field_id] = (scope, owner_key, field.k)
            return

        value = self._get_global_value(field.k, field) if scope == "global" else self._get_step_value(owner_key, field)
        text = self._display_editor_value(field, value)

        if field.tp == "enum" and field.one_of:
            from mluascript.frontends.tui.components.select import _Select
            
            options = [(opt.t or str(opt.v), str(opt.v)) for opt in field.one_of]
            select_value = None
            for _, val_str in options:
                if val_str == text:
                    select_value = val_str
                    break
            if select_value is None and options:
                select_value = options[0][1]

            select_widget = self._field_widgets.get(field_id)
            if not isinstance(select_widget, _Select):
                select_widget = _Select(options, value=select_value, id=field_id, classes="field-input")
                select_widget.display = is_active
                container.mount(select_widget)
                self._field_widgets[field_id] = select_widget
            else:
                if select_widget.value != select_value:
                    with select_widget.prevent(_Select.Changed):
                        select_widget.value = select_value
                select_widget.display = is_active
            self._field_input_map[field_id] = (scope, owner_key, field.k)
        else:
            input_widget = self._field_widgets.get(field_id)
            if not isinstance(input_widget, Input):
                input_widget = Input(value=text, id=field_id, classes="field-json-input" if field.tp in {"json", "list", "obj"} else "field-input")
                input_widget.display = is_active
                container.mount(input_widget)
                self._field_widgets[field_id] = input_widget
            else:
                if input_widget.value != text and not input_widget.has_focus:
                    with input_widget.prevent(Input.Changed):
                        input_widget.value = text
                input_widget.display = is_active
            self._field_input_map[field_id] = (scope, owner_key, field.k)

    def _mount_or_update_static(self, container: Vertical, widget_id: str, text: str, *, classes: str, display: bool = True) -> None:
        widget = self._field_widgets.get(widget_id)
        if isinstance(widget, Static):
            widget.update(text)
            widget.display = display
        else:
            widget = Static(text, id=widget_id, classes=classes)
            widget.display = display
            container.mount(widget)
            self._field_widgets[widget_id] = widget

    def _display_editor_value(self, field: TemplateVarDef, value: Any) -> str:
        if field.tp in {"json", "list", "obj"}:
            if isinstance(value, str):
                return value
            return json.dumps(value if value is not None else field.def_, ensure_ascii=False)
        if value is None:
            return ""
        return str(value)

    def _display_value(self, value: Any) -> str:
        if isinstance(value, (dict, list, tuple)):
            try:
                return json.dumps(value, ensure_ascii=False)
            except Exception:
                return str(value)
        return str(value)

    def _parse_field_value(self, field: TemplateVarDef, raw: str, fallback: Any) -> Any:
        text = raw.strip()
        if field.tp in {"json", "list", "obj"}:
            if not text:
                return field.def_
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                self.notify(f"字段 {field.k} 的 JSON 格式无效，已保留原值", severity="warning")
                return fallback
        if field.tp in {"int", "num"}:
            if not text:
                return field.def_
            try:
                number = float(text)
                return int(number) if field.tp == "int" else number
            except ValueError:
                self.notify(f"字段 {field.k} 需要数字，已保留原值", severity="warning")
                return fallback
        return text

    def _filter_template_tasks(self, tasks: list[TaskListItemView]) -> list[TaskListItemView]:
        result: list[TaskListItemView] = []
        for task in reversed(tasks):
            workflow_key = task.summary.get("workflow_key")
            script_path = task.summary.get("template_script_path")
            if workflow_key and script_path:
                result.append(task)
        return result

    def _build_saved_config_for_run(self) -> tuple[str, TemplateSavedConfig] | None:
        meta = self._get_current_meta()
        script_path = self._selected_script_path
        workflow_key = self._selected_workflow_key
        if meta is None or not script_path or not workflow_key:
            return None
        current_saved = self._selected_saved_config or TemplateSavedConfig(scriptPath=script_path)
        flow = self._get_current_flow(meta)
        if flow is None:
            return None
        saved_flow = current_saved.flows.get(workflow_key)
        globals_payload = dict(saved_flow.globals) if saved_flow is not None else {}
        step_enabled_payload = dict(saved_flow.stepEnabled) if saved_flow is not None else {}
        step_args_payload = dict(saved_flow.stepArgs) if saved_flow is not None else {}
        step_order_payload = list(saved_flow.stepOrder) if saved_flow is not None and saved_flow.stepOrder else [step.k for step in flow.steps]
        next_saved = TemplateSavedConfig.model_validate(
            {
                **current_saved.model_dump(),
                "scriptPath": script_path,
                "selectedFlowKey": workflow_key,
                "flows": {
                    **current_saved.model_dump().get("flows", {}),
                    workflow_key: {
                        "globals": globals_payload,
                        "stepEnabled": step_enabled_payload,
                        "stepArgs": step_args_payload,
                        "stepOrder": step_order_payload,
                    },
                },
            }
        )
        return workflow_key, next_saved

    def _persist_current_config(self) -> None:
        built = self._build_saved_config_for_run()
        if built is None or not self._selected_script_path:
            return
        _, saved = built
        self._selected_saved_config = self._template_store.save_saved_config(self._selected_script_path, saved)
        self._selected_config_path = self._template_store.get_saved_config_path(self._selected_script_path)

    def _get_or_create_saved_flow(self, saved: TemplateSavedConfig, workflow_key: str):
        saved_flow = saved.flows.get(workflow_key)
        if saved_flow is None:
            saved = TemplateSavedConfig.model_validate(saved.model_dump())
            saved_flow = saved.flows.get(workflow_key)
            if saved_flow is None:
                saved.flows[workflow_key] = cast(Any, {"globals": {}, "stepEnabled": {}, "stepArgs": {}, "stepOrder": []})
                saved = TemplateSavedConfig.model_validate(saved.model_dump())
                saved_flow = saved.flows.get(workflow_key)
        return saved, saved_flow

    def _set_global_field_value(self, field_key: str, value: Any) -> None:
        if not self._selected_workflow_key:
            return
        built = self._build_saved_config_for_run()
        if built is None:
            return
        workflow_key, saved = built
        saved_flow = saved.flows.get(workflow_key)
        if saved_flow is None:
            saved_flow = SavedFlowConfig()
            saved.flows[workflow_key] = saved_flow
        saved_flow.globals[field_key] = value
        self._selected_saved_config = saved
        self._persist_current_config()
        self._refresh_all()

    def _set_step_field_value(self, step_key: str, field_key: str, value: Any) -> None:
        built = self._build_saved_config_for_run()
        if built is None:
            return
        workflow_key, saved = built
        saved_flow = saved.flows.get(workflow_key)
        if saved_flow is None:
            saved_flow = SavedFlowConfig()
            saved.flows[workflow_key] = saved_flow
        payload = dict(saved_flow.stepArgs.get(step_key, {}))
        payload[field_key] = value
        saved_flow.stepArgs[step_key] = payload
        self._selected_saved_config = saved
        self._persist_current_config()
        self._refresh_all()

    def _set_step_enabled(self, step_key: str, enabled: bool) -> None:
        built = self._build_saved_config_for_run()
        if built is None:
            return
        workflow_key, saved = built
        saved_flow = saved.flows.get(workflow_key)
        if saved_flow is None:
            saved_flow = SavedFlowConfig()
            saved.flows[workflow_key] = saved_flow
        saved_flow.stepEnabled[step_key] = enabled
        self._selected_saved_config = saved
        self._persist_current_config()
        self._refresh_all()

    def _move_step(self, step_key: str, direction: str) -> None:
        flow = self._get_current_flow()
        built = self._build_saved_config_for_run()
        if flow is None or built is None:
            return
        workflow_key, saved = built
        saved_flow = saved.flows.get(workflow_key)
        if saved_flow is None:
            saved_flow = SavedFlowConfig(stepOrder=[step.k for step in flow.steps])
            saved.flows[workflow_key] = saved_flow
        order = list(saved_flow.stepOrder or [step.k for step in flow.steps])
        if step_key not in order:
            order.append(step_key)
        index = order.index(step_key)
        if direction == "up" and index > 0:
            order[index - 1], order[index] = order[index], order[index - 1]
        elif direction == "down" and index < len(order) - 1:
            order[index + 1], order[index] = order[index], order[index + 1]
        saved_flow.stepOrder = order
        self._selected_saved_config = saved
        self._persist_current_config()
        self._refresh_all()

    def action_refresh_templates(self) -> None:
        self._selected_script_meta = None
        self._refresh_all()
        self.notify("模板列表已刷新")

    def action_run_selected_workflow(self) -> None:
        self._run_current_template()

    @on(Tabs.TabActivated, "#template-workflow-tabs")
    def _on_workflow_tab_activated(self, event: Tabs.TabActivated) -> None:
        pane_id = event.tab.id or ""
        if not pane_id.startswith("template-flow-pane-"):
            return
        try:
            index = int(pane_id.removeprefix("template-flow-pane-"))
        except ValueError:
            return
        meta = self._get_current_meta()
        if meta is None or index >= len(meta.flows):
            return
        self._selected_workflow_key = meta.flows[index].k
        self._selected_step_key = None
        self._refresh_all()

    def _load_template_script(self, payload: dict[str, Any]) -> None:
        script_path = str(payload.get("path") or "").strip()
        if not script_path:
            return
        if self._selected_script_path != script_path:
            self._selected_script_meta = None
        self._selected_script_path = script_path
        workflow_key = str(payload.get("workflowKey") or "").strip()
        if workflow_key:
            self._selected_workflow_key = workflow_key
        self._selected_step_key = None
        self._sync_selected_template()
        self._load_selected_template_state()
        self._render_workflow_tabs()
        self._render_template_summary()
        self._render_globals_panel()
        self._render_step_list()
        self._render_step_detail()
        self._render_meta_panel()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button = event.button
        if button.id == "btn-template-run":
            self.action_run_selected_workflow()
            return
        if button.id and button.id.startswith("step-list-up-"):
            try:
                index = int(button.id.removeprefix("step-list-up-"))
                step_key = self._step_button_map.get(f"template-step-{index}")
                if step_key:
                    self._move_step(step_key, "up")
            except ValueError:
                pass
            return
        if button.id and button.id.startswith("step-list-down-"):
            try:
                index = int(button.id.removeprefix("step-list-down-"))
                step_key = self._step_button_map.get(f"template-step-{index}")
                if step_key:
                    self._move_step(step_key, "down")
            except ValueError:
                pass
            return
        if button.name in self._workflow_button_map:
            self._selected_workflow_key = self._workflow_button_map[button.name]
            self._selected_step_key = None
            self._refresh_all()
            return
        if button.name in self._step_button_map:
            self._selected_step_key = self._step_button_map[button.name]
            self._refresh_all()
            tabs = self.query_one("#template-run-tabs", TabbedContent)
            tabs.active = "template-run-tab-step"
            return

    from mluascript.frontends.tui.components.select import _Select
    @on(Input.Changed)
    @on(_Select.Changed)
    def _on_input_changed(self, event: Input.Changed | _Select.Changed) -> None:
        if isinstance(event, Input.Changed):
            input_id = event.input.id or ""
            raw_value = event.value
        else:
            input_id = event.select.id or ""
            raw_value = str(event.value) if event.value is not None else ""
            
        binding = self._field_input_map.get(input_id)
        if binding is None:
            return
        scope, owner_key, field_key = binding
        meta = self._get_current_meta()
        if meta is None:
            return
        field = meta.vars.get(field_key)
        if field is None:
            return
        fallback = self._get_global_value(field_key, field) if scope == "global" else self._get_step_value(owner_key, field)
        value = self._parse_field_value(field, raw_value, fallback)
        if scope == "global":
            self._set_global_field_value(field_key, value)
        else:
            self._set_step_field_value(owner_key, field_key, value)

    @on(Switch.Changed)
    def _on_switch_changed(self, event: Switch.Changed) -> None:
        switch_id = event.switch.id or ""
        binding = self._field_switch_map.get(switch_id)
        if binding is None:
            return
        scope, owner_key, field_key = binding
        if scope == "step_enabled":
            self._set_step_enabled(owner_key, event.value)
            return
        if scope == "global":
            self._set_global_field_value(field_key, bool(event.value))
            return
        self._set_step_field_value(owner_key, field_key, bool(event.value))

    @work(thread=True)
    def _run_current_template(self) -> None:
        built = self._build_saved_config_for_run()
        script_path = self._selected_script_path
        if built is None or not script_path:
            self.app.call_from_thread(self.notify, "当前没有可执行的模板工作流", severity="warning")
            return
        workflow_key, saved = built
        try:
            meta = self._template_store.get_template_meta(script_path)
            if meta is None:
                self.app.call_from_thread(self.notify, "脚本未声明模板元数据", severity="error")
                return
            saved_config = self._template_store.save_saved_config(script_path, saved)
            runtime_code = self._template_store.build_runtime_script(meta, saved_config, flow_key=workflow_key)
            source_code = self._control.read_script(script_path)
            target = self._control.get_device_overview().connection.label or "LOCAL"
            task_id = self._control.run_script(script_path, f"{source_code}\n\n{runtime_code}\n", target)
            self.app.call_from_thread(self.notify, f"模板工作流已启动: {task_id}", severity="information")
            self._selected_saved_config = saved_config
            self.app.call_from_thread(self._refresh_all)
        except Exception as exc:
            self.app.call_from_thread(self.notify, f"启动模板工作流失败: {exc}", severity="error")

    def _clear_buttons(self, button_map: dict[str, Button]) -> None:
        for button in list(button_map.values()):
            button.remove()
        button_map.clear()
