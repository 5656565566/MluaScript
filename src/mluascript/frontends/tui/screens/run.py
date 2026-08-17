"""任务运行页面"""

from __future__ import annotations

import time
from typing import Any, cast

from textual import work
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.timer import Timer
from textual.widgets import Button, Markdown, RichLog, Static, TabbedContent, TabPane

from mluascript.control.facade import get_control_facade
from mluascript.control.state.models import TaskListItemView
from mluascript.control.workspace import ArtifactReadme, RunnableArtifact, get_template_store
from mluascript.frontends.tui.components.pagination import paginate_items


TASK_PAGE_SIZE = 10
SCRIPT_PAGE_SIZE = 10


def _paginate_tasks(
    tasks: list[TaskListItemView],
    page_index: int,
    page_size: int = TASK_PAGE_SIZE,
) -> tuple[list[TaskListItemView], int, int]:
    """按新任务优先分页，并将越界页码收敛到有效范围。"""

    ordered = list(reversed(tasks))
    return paginate_items(ordered, page_index, page_size)


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

    .artifact-script-row {
        height: 3;
        width: 100%;
        align-vertical: middle;
    }

    Button.artifact-run-btn {
        width: 1fr;
    }

    Button.artifact-readme-btn {
        width: 1fr;
    }

    .artifact-script-row Button.artifact-run-btn {
        width: 10;
        min-width: 10;
        height: 3;
        margin: 0 0 0 1;
    }

    #task-pagination {
        height: auto;
        width: 100%;
        align-horizontal: center;
        margin: 0 0 1 0;
    }

    #script-pagination {
        height: auto;
        width: 100%;
        align-horizontal: center;
        margin: 0 0 1 0;
    }

    #task-page-status,
    #script-page-status {
        width: auto;
        min-width: 24;
        height: 3;
        content-align: center middle;
        margin: 0 1;
    }

    .task-page-btn,
    .script-page-btn {
        width: 10;
        min-width: 10;
        margin: 0;
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
        self._script_page_index = 0
        self._task_page_index = 0
        self._script_button_action_map: dict[str, tuple[str, str]] = {}
        self._readme_button_name_map: dict[str, str] = {}
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
        self._output_version: int = -1
        self._available_render_key: tuple[Any, ...] | None = None
        self._available_scripts_cache: list[Any] = []
        self._artifact_cache: list[RunnableArtifact] = []
        self._last_resource_refresh = 0.0

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
                    with Horizontal(id="script-pagination"):
                        yield Button(
                            "上一页",
                            id="script-page-previous",
                            name="script-page-previous",
                            classes="script-page-btn",
                        )
                        yield Static("第 0 / 0 页", id="script-page-status")
                        yield Button(
                            "下一页",
                            id="script-page-next",
                            name="script-page-next",
                            classes="script-page-btn",
                        )

            with TabPane("任务状态", id="run-tab-status"):
                with ScrollableContainer(classes="tab-scroll-area"):
                    yield Markdown("### 已创建任务")
                    yield Vertical(id="task-list")
                    with Horizontal(id="task-pagination"):
                        yield Button(
                            "上一页",
                            id="task-page-previous",
                            name="task-page-previous",
                            classes="task-page-btn",
                        )
                        yield Static("第 0 / 0 页", id="task-page-status")
                        yield Button(
                            "下一页",
                            id="task-page-next",
                            name="task-page-next",
                            classes="task-page-btn",
                        )
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
                    yield RichLog(id="runtime-log-view", markup=False, wrap=True, auto_scroll=True, max_lines=200)

            with TabPane("包说明", id="run-tab-readme"):
                with ScrollableContainer(classes="tab-scroll-area"):
                    yield Static("当前未选择构建包", id="artifact-readme-summary", classes="panel-desc")
                    yield Markdown("请选择带 README 的构建包。", id="artifact-readme-view")

    def on_mount(self) -> None:
        self._refresh_timer = self.set_interval(0.5, self._refresh_all)
        self.set_active(getattr(self.app, "active_tab", None) == self.id)

    def set_active(self, active: bool) -> None:
        """仅在任务页可见时轮询和渲染，避免隐藏页面持续占用事件循环。"""

        if self._refresh_timer is None:
            return
        if active:
            self._refresh_timer.resume()
            self._refresh_all()
        else:
            self._refresh_timer.pause()

    def _refresh_all(self, *, force_resources: bool = False) -> None:
        now = time.monotonic()
        if force_resources or now - self._last_resource_refresh >= 5.0:
            self._available_scripts_cache = self._control.list_scripts()
            self._artifact_cache = self._control.list_build_artifacts()
            self._last_resource_refresh = now
        tasks = self._control.list_task_views()
        self._sync_selected_task(tasks)
        self._render_available_scripts(self._available_scripts_cache, self._artifact_cache)
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

    def _render_available_scripts(self, scripts, artifacts: list[RunnableArtifact]) -> None:
        container = self.query_one("#available-script-list", Vertical)
        kind_labels = {"package": "脚本包", "maa": "Maa 包", "lua": "Lua"}
        resources: list[tuple[str, str, str, bool]] = [
            (
                "artifact",
                artifact.id,
                f"[{kind_labels[artifact.kind]}] {artifact.name}"
                f"{f' · {artifact.version}' if artifact.version else ''}",
                artifact.has_readme,
            )
            for artifact in artifacts
        ]
        resources.extend(("script", script.path, script.path, False) for script in scripts)
        page_resources, self._script_page_index, total_pages = paginate_items(
            resources,
            self._script_page_index,
            SCRIPT_PAGE_SIZE,
        )
        self._render_script_pagination(len(resources), total_pages)
        render_key = (self._script_page_index, tuple(page_resources))
        if self._available_render_key == render_key:
            return

        container.remove_children()
        self._script_buttons.clear()
        self._script_button_action_map = {
            f"script-run-{index}": (kind, identifier)
            for index, (kind, identifier, _label, _has_readme) in enumerate(page_resources)
        }
        self._readme_button_name_map = {
            f"artifact-readme-{index}": identifier
            for index, (kind, identifier, _label, has_readme) in enumerate(page_resources)
            if kind == "artifact" and has_readme
        }

        if not page_resources:
            self._empty_script_widget = Static("当前没有扫描到构建产物或 Lua 脚本", classes="task-item")
            container.mount(self._empty_script_widget)
            self._available_render_key = render_key
            return

        self._empty_script_widget = None
        for index, (kind, _identifier, label, has_readme) in enumerate(page_resources):
            run_name = f"script-run-{index}"
            run_button = Button(f"运行 {label}", name=run_name, classes="script-btn artifact-run-btn")
            self._script_buttons[run_name] = run_button
            if kind == "artifact" and has_readme:
                readme_button = Button(
                    f"查看说明 {label}",
                    name=f"artifact-readme-{index}",
                    classes="artifact-readme-btn",
                )
                run_button.label = "运行"
                container.mount(Horizontal(readme_button, run_button, classes="artifact-script-row"))
            else:
                container.mount(run_button)
        self._available_render_key = render_key

    def _render_script_pagination(self, script_count: int, total_pages: int) -> None:
        previous = self.query_one("#script-page-previous", Button)
        next_page = self.query_one("#script-page-next", Button)
        status = self.query_one("#script-page-status", Static)
        if total_pages == 0:
            status.update("第 0 / 0 页 · 共 0 项")
            previous.disabled = True
            next_page.disabled = True
            return
        status.update(f"第 {self._script_page_index + 1} / {total_pages} 页 · 共 {script_count} 项")
        previous.disabled = self._script_page_index == 0
        next_page.disabled = self._script_page_index >= total_pages - 1

    def _render_task_list(self, tasks: list[TaskListItemView]) -> None:
        container = self.query_one("#task-list", Vertical)
        page_tasks, self._task_page_index, total_pages = _paginate_tasks(tasks, self._task_page_index)
        self._render_task_pagination(len(tasks), total_pages)
        self._task_button_name_map = {
            f"task-select-{index}": task.task_id for index, task in enumerate(page_tasks)
        }
        target_names = set(self._task_button_name_map.keys())

        if not page_tasks:
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

        for index, task in enumerate(page_tasks):
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

    def _render_task_pagination(self, task_count: int, total_pages: int) -> None:
        previous = self.query_one("#task-page-previous", Button)
        next_page = self.query_one("#task-page-next", Button)
        status = self.query_one("#task-page-status", Static)
        if total_pages == 0:
            status.update("第 0 / 0 页 · 共 0 项")
            previous.disabled = True
            next_page.disabled = True
            return
        status.update(f"第 {self._task_page_index + 1} / {total_pages} 页 · 共 {task_count} 项")
        previous.disabled = self._task_page_index == 0
        next_page.disabled = self._task_page_index >= total_pages - 1

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
                self._output_version = -1
            return

        output_summary.update(f"运行输出: {task.title or task.name or task.task_id}")
        log_summary.update(f"运行日志: {task.title or task.name or task.task_id}")

        if self._last_rendered_task_id != task.task_id:
            output_log.clear()
            log_view.clear()
            self._last_rendered_task_id = task.task_id
            self._output_line_count = 0
            self._log_line_count = 0
            self._output_version = -1

        output_lines = output.items if output is not None else []
        output_version = output.version if output is not None else -1

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

        if output_version != self._output_version:
            if len(output_lines) < self._output_line_count:
                output_log.clear()
                self._output_line_count = 0
            if len(output_lines) == self._output_line_count:
                output_log.clear()
                self._output_line_count = 0
            for line in output_lines[self._output_line_count:]:
                output_log.write(Text.from_ansi(line))
            self._output_line_count = len(output_lines)
            self._output_version = output_version

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
        self._refresh_all(force_resources=True)
        self.notify("已刷新任务状态")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_name = event.button.name or ""
        if button_name == "script-page-previous":
            self._script_page_index = max(0, self._script_page_index - 1)
            self._refresh_all()
            return
        if button_name == "script-page-next":
            self._script_page_index += 1
            self._refresh_all()
            return
        if button_name in self._readme_button_name_map:
            self._activate_tab("run-tab-readme")
            self.query_one("#artifact-readme-summary", Static).update("正在读取包说明...")
            self.query_one("#artifact-readme-view", Markdown).update("正在读取包说明，请稍候。")
            self._open_artifact_readme(self._readme_button_name_map[button_name])
            return
        if button_name == "task-page-previous":
            self._task_page_index = max(0, self._task_page_index - 1)
            self._refresh_all()
            return
        if button_name == "task-page-next":
            self._task_page_index += 1
            self._refresh_all()
            return
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
            action = self._script_button_action_map.get(button_name)
            if action is not None:
                kind, identifier = action
                if kind == "artifact":
                    self._run_artifact(identifier)
                else:
                    self._open_script(identifier)

    @work(thread=True)
    def _open_artifact_readme(self, artifact_id: str) -> None:
        try:
            readme = self._control.get_artifact_readme(artifact_id)
            self.app.call_from_thread(self._show_artifact_readme, readme)
        except Exception as exc:
            self.app.call_from_thread(self._show_artifact_readme_error, str(exc))

    def _show_artifact_readme(self, readme: ArtifactReadme) -> None:
        self.query_one("#artifact-readme-summary", Static).update(f"{readme.name} · {readme.path}")
        self.query_one("#artifact-readme-view", Markdown).update(readme.markdown)
        self._activate_tab("run-tab-readme")

    def _show_artifact_readme_error(self, message: str) -> None:
        self.query_one("#artifact-readme-summary", Static).update("包说明读取失败")
        self.query_one("#artifact-readme-view", Markdown).update(f"无法读取包说明：{message}")
        self._activate_tab("run-tab-readme")
        self.notify(f"读取包说明失败: {message}", severity="error")

    @work(thread=True)
    def _run_artifact(self, artifact_id: str) -> None:
        try:
            overview = self._control.get_device_overview()
            target = overview.connection.label or "LOCAL"
            task_id = self._control.run_artifact(artifact_id, target)
            self._selected_task_id = task_id
            self._task_page_index = 0
            self.app.call_from_thread(self._activate_tab, "run-tab-status")
            self.app.call_from_thread(self.notify, f"已启动构建产物: {task_id}")
            self.app.call_from_thread(self._refresh_all)
        except Exception as exc:
            self.app.call_from_thread(self.notify, f"启动构建产物失败: {exc}", severity="error")

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
            self._task_page_index = 0
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
