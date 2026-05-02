"""任务运行页面"""

from __future__ import annotations

from typing import Any, cast

from textual import work
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer, Vertical
from textual.timer import Timer
from textual.widgets import Button, Markdown, RichLog, Static, TabbedContent, TabPane

from mluascript.control.facade import get_control_facade
from mluascript.control.state.models import TaskListItemView
from mluascript.control.workspace import get_template_store


class RunScreen(ScrollableContainer):
    DEFAULT_CSS = """
    RunScreen {
        width: 100%;
        height: 1fr;
    }

    .tab-scroll-area {
        height: 1fr;
        padding: 0 1;
        overflow-y: auto;
    }

    .tab-area {
        height: 1fr;
        padding: 0 1;
    }

    #available-script-list,
    #task-list,
    #task-detail {
        height: auto;
        width: 100%;
    }

    #runtime-output-log,
    #runtime-log-view {
        height: 1fr;
        width: 100%;
        border: solid $accent;
        margin-top: 1;
    }

	.task-btn {
	    margin: 1 0;
	    width: 100%;
	    background: #2f5d31;
	}

	.task-btn.-active {
	    background: #1E88E5 !important;
	    color: white !important;
	    text-style: bold;
	}

	.task-btn:hover {
	    background: #4CAF50 !important;
	}

	.task-btn.-active:hover {
	    background: #1565C0 !important;
	}

	   Button.script-btn {
	       background: #2E7D32;
	       margin: 1 0;
	       width: 100%;
	   }

	   Button.nav-btn {
	       margin: 1 0;
	       width: 100%;
	   }

	   Button.status-btn {
	       margin: 1 0;
	       width: 100%;
	   }

    .panel-desc {
        color: $text-muted;
        margin-bottom: 1;
    }

    .task-item {
        margin: 0 0 1 0;
    }
    """

    BINDINGS = [
        Binding("r", "refresh_tasks", "刷新", tooltip="重新获取任务列表"),
        Binding("s", "stop_tasks", "停止全部运行中任务", tooltip="停止正在运行的任务"),
    ]

    def __init__(self, name: str | None = None, id: str | None = None, classes: str | None = None) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._refresh_timer: Timer | None = None
        self._selected_task_id: str | None = None
        self._script_button_name_map: dict[str, str] = {}
        self._task_button_name_map: dict[str, str] = {}
        self._task_action_name_map: dict[str, tuple[str, str]] = {}
        self._script_buttons: dict[str, Button] = {}
        self._task_buttons: dict[str, Button] = {}
        self._detail_rows: dict[str, Static] = {}
        self._detail_buttons: dict[str, Button] = {}
        self._empty_script_widget: Static | None = None
        self._empty_task_widget: Static | None = None
        self._empty_detail_widget: Static | None = None
        self._last_rendered_task_id: str | None = None
        self._output_line_count: int = 0
        self._log_line_count: int = 0

    @property
    def _control(self):
        return get_control_facade()

    def compose(self) -> ComposeResult:
        with TabbedContent(id="run-tabs"):
            with TabPane("任务列表", id="run-tab-list"):
                with ScrollableContainer(classes="tab-scroll-area"):
                    yield Markdown("### 可运行脚本")
                    yield Static("点击脚本即可直接创建 Lua 运行任务", classes="panel-desc")
                    yield Vertical(id="available-script-list")

            with TabPane("任务状态", id="run-tab-status"):
                with ScrollableContainer(classes="tab-scroll-area"):
                    yield Markdown("### 已创建任务")
                    yield Vertical(id="task-list")
                    yield Markdown("### 当前任务详情")
                    yield Static("当前未选择任务", id="selected-task-summary")
                    yield Vertical(id="task-detail")

            with TabPane("运行输出", id="run-tab-output"):
                with Vertical(classes="tab-area"):
                    yield Static("运行输出: 当前未选择脚本任务", id="runtime-output-summary")
                    yield RichLog(id="runtime-output-log", markup=False, wrap=True, auto_scroll=True)

            with TabPane("运行日志", id="run-tab-log"):
                with Vertical(classes="tab-area"):
                    yield Static("运行日志: 当前未选择脚本任务", id="runtime-log-summary")
                    yield RichLog(id="runtime-log-view", markup=False, wrap=True, auto_scroll=True)

    def on_mount(self) -> None:
        self._refresh_timer = self.set_interval(0.5, self._refresh_all)
        self._refresh_all()

    def _refresh_all(self) -> None:
        scripts = self._control.list_scripts()
        tasks = self._control.list_task_views()
        self._sync_selected_task(tasks)
        self._render_available_scripts(scripts)
        self._render_task_list(tasks)
        self._render_status_panel(tasks)
        self._render_runtime_views(tasks)

    def _sync_selected_task(self, tasks: list[TaskListItemView]) -> None:
        if not tasks:
            self._selected_task_id = None
            return

        selected = next((task for task in tasks if task.task_id == self._selected_task_id), None)
        if selected is None:
            selected = tasks[-1]
            self._selected_task_id = selected.task_id

    def _render_available_scripts(self, scripts) -> None:
        container = self.query_one("#available-script-list", Vertical)
        self._script_button_name_map = {f"script-run-{index}": script.path for index, script in enumerate(scripts)}
        target_names = set(self._script_button_name_map.keys())

        if not scripts:
            for name, button in list(self._script_buttons.items()):
                button.remove()
                self._script_buttons.pop(name, None)
            if self._empty_script_widget is None:
                self._empty_script_widget = Static("当前没有扫描到 Lua 脚本 请检查配置路径下是否存在顶层 `.lua` 文件", classes="task-item")
                container.mount(self._empty_script_widget)
            return

        if self._empty_script_widget is not None:
            self._empty_script_widget.remove()
            self._empty_script_widget = None

        for name, path in self._script_button_name_map.items():
            button = self._script_buttons.get(name)
            label = f"运行 {path}"
            if button is None:
                button = Button(label, name=name, classes="script-btn")
                self._script_buttons[name] = button
                container.mount(button)
            else:
                button.label = label
                button.display = True

        for name, button in list(self._script_buttons.items()):
            if name not in target_names:
                button.remove()
                self._script_buttons.pop(name, None)

    def _render_task_list(self, tasks: list[TaskListItemView]) -> None:
        container = self.query_one("#task-list", Vertical)
        ordered = list(reversed(tasks))
        self._task_button_name_map = {f"task-select-{index}": task.task_id for index, task in enumerate(ordered)}
        target_names = set(self._task_button_name_map.keys())

        if not ordered:
            for name, button in list(self._task_buttons.items()):
                button.remove()
                self._task_buttons.pop(name, None)
            if self._empty_task_widget is None:
                self._empty_task_widget = Static("当前还没有创建任何运行任务", classes="task-item")
                container.mount(self._empty_task_widget)
            return

        if self._empty_task_widget is not None:
            self._empty_task_widget.remove()
            self._empty_task_widget = None

        for index, task in enumerate(ordered):
            name = f"task-select-{index}"
            label = self._build_task_label(task)
            button = self._task_buttons.get(name)
            
            if button is None:
                button = Button(label, name=name, classes="task-btn")
                self._task_buttons[name] = button
                container.mount(button)
            else:
                button.label = label
                button.display = True
                
            if task.task_id == self._selected_task_id:
                button.add_class("-active")
            else:
                button.remove_class("-active")

        for name, button in list(self._task_buttons.items()):
            if name not in target_names:
                button.remove()
                self._task_buttons.pop(name, None)

    def _render_status_panel(self, tasks: list[TaskListItemView]) -> None:
        summary = self.query_one("#selected-task-summary", Static)
        container = self.query_one("#task-detail", Vertical)
        task = self._find_selected_task(tasks)
        detail = self._control.get_task_detail_view(task.task_id) if task is not None else None
        self._task_action_name_map.clear()

        if task is None or detail is None:
            summary.update("当前未选择任务")
            for widget in list(self._detail_rows.values()):
                widget.remove()
            for widget in list(self._detail_buttons.values()):
                widget.remove()
            self._detail_rows.clear()
            self._detail_buttons.clear()
            if self._empty_detail_widget is None:
                self._empty_detail_widget = Static("暂无任务详情", classes="task-item")
                container.mount(self._empty_detail_widget)
            return

        if self._empty_detail_widget is not None:
            self._empty_detail_widget.remove()
            self._empty_detail_widget = None

        summary.update(self._build_task_summary(task))
        detail_texts: dict[str, str] = {
            "task_id": f"任务 ID: {detail.task_id}",
            "kind": f"类型: {detail.kind}",
            "status": f"状态: {detail.status}",
            "target": f"目标: {detail.target}",
        }
        if detail.title:
            detail_texts["title"] = f"标题: {detail.title}"
        if detail.error:
            detail_texts["error"] = f"错误: {detail.error}"
        if detail.result is not None:
            detail_texts["result"] = f"结果: {detail.result}"
        if detail.summary:
            detail_texts["summary"] = f"摘要: {detail.summary}"

        for key, text in detail_texts.items():
            widget = self._detail_rows.get(key)
            if widget is None:
                widget = Static(text, classes="task-item")
                self._detail_rows[key] = widget
                container.mount(widget)
            else:
                widget.update(text)
                widget.display = True

        for key, widget in list(self._detail_rows.items()):
            if key not in detail_texts:
                widget.remove()
                self._detail_rows.pop(key, None)

        action_specs = {
            "output": ("task-nav-output", "查看运行输出", detail.kind != "script" or not detail.capabilities.has_output),
            "log": ("task-nav-log", "查看运行日志", detail.kind != "script" or not detail.capabilities.has_logs),
            "stop": ("task-stop", "停止该任务", not detail.capabilities.can_stop),
            "remove": ("task-remove", "删除任务记录", not detail.capabilities.can_remove),
        }

        for action, (name, label, disabled) in action_specs.items():
            self._task_action_name_map[name] = (action, task.task_id)
            button = self._detail_buttons.get(action)
            classes = "nav-btn" if action in {"output", "log"} else "status-btn"
            if button is None:
                button = Button(label, name=name, classes=classes, disabled=disabled)
                self._detail_buttons[action] = button
                container.mount(button)
            else:
                button.label = label
                button.disabled = disabled
                button.display = True

        for action, button in list(self._detail_buttons.items()):
            if action not in action_specs:
                button.remove()
                self._detail_buttons.pop(action, None)

    def _render_runtime_views(self, tasks: list[TaskListItemView]) -> None:
        output_summary = self.query_one("#runtime-output-summary", Static)
        output_log = self.query_one("#runtime-output-log", RichLog)
        log_summary = self.query_one("#runtime-log-summary", Static)
        log_view = self.query_one("#runtime-log-view", RichLog)

        task = self._find_selected_task(tasks)
        logs = self._control.get_task_logs(task.task_id) if task is not None else None
        output = self._control.get_task_output(task.task_id) if task is not None else None
        if task is None or task.kind != "script":
            output_summary.update("运行输出: 当前未选择脚本任务")
            log_summary.update("运行日志: 当前未选择脚本任务")

            if self._last_rendered_task_id is not None:
                output_log.clear()
                log_view.clear()
                self._last_rendered_task_id = None
                self._output_line_count = 0
                self._log_line_count = 0
            return

        output_summary.update(f"运行输出: {task.title or task.name or task.task_id}")
        log_summary.update(f"运行日志: {task.title or task.name or task.task_id}")

        if self._last_rendered_task_id != task.task_id:
            output_log.clear()
            log_view.clear()
            self._last_rendered_task_id = task.task_id
            self._output_line_count = 0
            self._log_line_count = 0

        output_lines = output.items if output is not None else []

        log_lines = []
        if logs is not None:
            for item in logs.items:
                level = str(item.level or "INFO").upper()
                msg = str(item.message or "")
                color = "white"
                if level in ("ERROR", "FATAL"):
                    color = "red"
                elif level in ("WARN", "WARNING"):
                    color = "yellow"
                elif level in ("INFO", "SUCCESS"):
                    color = "green"
                elif level == "DEBUG":
                    color = "blue"
                elif level == "TRACE":
                    color = "cyan"
                log_lines.append(f"[{color}][{level}][/{color}] {msg}")

        if len(output_lines) > self._output_line_count:
            for line in output_lines[self._output_line_count:]:
                output_log.write(Text.from_ansi(line))
            self._output_line_count = len(output_lines)

        if len(log_lines) > self._log_line_count:
            for line in log_lines[self._log_line_count:]:
                log_view.write(Text.from_markup(line))
            self._log_line_count = len(log_lines)

    def _find_selected_task(self, tasks: list[TaskListItemView]) -> TaskListItemView | None:
        if self._selected_task_id is None:
            return None
        return next((task for task in tasks if task.task_id == self._selected_task_id), None)

    def _build_task_label(self, task: TaskListItemView) -> str:
        title = task.title or task.name or task.task_id
        return f"[{task.kind.upper()}][{task.status.upper()}] {title} -> {task.target}"

    def _build_task_summary(self, task: TaskListItemView) -> str:
        title = task.title or task.name or task.task_id
        return f"当前任务：{title} | {task.kind} | {task.status}"

    def _activate_tab(self, pane_id: str) -> None:
        self.query_one("#run-tabs", TabbedContent).active = pane_id

    def action_refresh_tasks(self) -> None:
        self._refresh_all()
        self.notify("已刷新任务状态")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_name = event.button.name or ""
        if button_name.startswith("task-select-"):
            task_id = self._task_button_name_map.get(button_name)
            if task_id:
                self._selected_task_id = task_id
                self._activate_tab("run-tab-status")
                self._refresh_all()
            return
        if button_name in self._task_action_name_map:
            action, task_id = self._task_action_name_map[button_name]
            if action != "remove":
                self._selected_task_id = task_id
            if action == "stop":
                self._stop_task(task_id)
                return
            if action == "remove":
                self._remove_task(task_id)
                return
            if action == "output":
                self._activate_tab("run-tab-output")
                self.set_timer(0.05, lambda: self.query_one("#runtime-output-log", RichLog).focus())
            elif action == "log":
                self._activate_tab("run-tab-log")
                self.set_timer(0.05, lambda: self.query_one("#runtime-output-log", RichLog).focus())
            self._refresh_all()
            return
        if button_name.startswith("script-run-"):
            script_path = self._script_button_name_map.get(button_name)
            if script_path:
                self._open_script(script_path)

    @work(thread=True)
    def _open_script(self, script_path: str) -> None:
        try:
            meta = get_template_store().get_template_meta(script_path)
            if meta is not None and meta.flows:
                template_screen = self.app.query_one("#template-run")
                loader = getattr(template_screen, "_load_template_script", None)
                if callable(loader):
                    self.app.call_from_thread(loader, {"path": script_path, "name": script_path.split("/")[-1]})
                self.app.call_from_thread(cast("Any", self.app).action_switch_tab, "template-run")
                self.app.call_from_thread(self.notify, f"已打开模板执行页: {script_path}")
                return
            self._run_script(script_path)
        except Exception as exc:
            self.app.call_from_thread(self.notify, f"打开脚本失败: {exc}", severity="error")

    @work(thread=True)
    def _run_script(self, script_path: str) -> None:
        try:
            overview = self._control.get_device_overview()
            target = overview.connection.label
            if not target:
                self.app.call_from_thread(self.notify, "当前未连接设备", severity="warning")
                return
            code = self._control.read_script(script_path)
            task_id = self._control.run_script(script_path, code, target)
            self._selected_task_id = task_id
            self.app.call_from_thread(self._activate_tab, "run-tab-status")
            self.app.call_from_thread(self.notify, f"已启动 Lua 任务: {script_path} -> {task_id}")
            self.app.call_from_thread(self._refresh_all)
        except Exception as exc:
            self.app.call_from_thread(self.notify, f"启动 Lua 任务失败: {exc}", severity="error")

    @work(thread=True)
    def _stop_task(self, task_id: str) -> None:
        task = self._control.get_task_detail_view(task_id)
        if task is None:
            self.app.call_from_thread(self.notify, "任务不存在", severity="warning")
            return
        if task.kind == "script":
            self._control.stop_script(task_id)
        else:
            self._control.stop_pipeline(task_id)
        self.app.call_from_thread(self._refresh_all)
        self.app.call_from_thread(self.notify, f"已请求停止任务 {task_id}")

    def _remove_task(self, task_id: str) -> None:
        removed = self._control.remove_task(task_id)
        if self._selected_task_id == task_id:
            self._selected_task_id = None
        self._refresh_all()
        self.notify("已删除任务记录" if removed else "任务不存在", severity="warning" if not removed else "information")

    @work(thread=True)
    def action_stop_tasks(self) -> None:
        tasks = self._control.list_task_views()
        stopped = 0
        for task in tasks:
            if not task.capabilities.can_stop:
                continue
            if task.kind == "script":
                self._control.stop_script(task.task_id)
            else:
                self._control.stop_pipeline(task.task_id)
            stopped += 1
        self.app.call_from_thread(self._refresh_all)
        self.app.call_from_thread(self.notify, f"已请求停止 {stopped} 个运行中任务")
