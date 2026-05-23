from __future__ import annotations

from typing import Any

from mluascript.maa.connections import current_desktop_label
from mluascript.runtime.output_buffer import TaskOutputBuffer

from .devices import ConnectAdbRequest, DeviceActionResult, DeviceOverview, get_device_facade
from .execution.manager import get_execution_manager
from .state.manager import get_state_manager
from .state.models import (
    SystemState,
    TaskCapabilities,
    TaskDetailView,
    TaskInfo,
    TaskListItemView,
    TaskLogEntryView,
    TaskLogsView,
    TaskOutputView,
)
from .workspace.manager import get_workspace_manager
from .workspace.models import ScriptInfo


class ControlFacade:
    """应用控制层入口"""

    def __init__(self) -> None:
        self.exec_mgr = get_execution_manager()
        self.state_mgr = get_state_manager()
        self.workspace_mgr = get_workspace_manager()
        self.device_facade = get_device_facade()

    def list_scripts(self) -> list[ScriptInfo]:
        """获取工作区下可用脚本"""
        return self.workspace_mgr.list_scripts()

    def read_script(self, rel_path: str) -> str:
        """读取工作区脚本"""
        return self.workspace_mgr.read_script(rel_path)

    def get_system_state(self) -> SystemState:
        """获取系统整体执行与连接状态"""
        state = self.state_mgr.get_state()
        overview = self.device_facade.get_overview()
        state.connected_sessions = [overview.connection.label] if overview.connection.label else []
        return state

    def _build_task_summary(self, task: TaskInfo) -> dict[str, Any]:
        keys = (
            "script_path",
            "entry",
            "project_path",
        )
        summary: dict[str, Any] = {key: task.summary.get(key) for key in keys if key in task.summary}
        return summary

    def _build_task_capabilities(self, task: TaskInfo) -> TaskCapabilities:
        log_buffer = task.log_buffer
        print_buffer = task.print_buffer
        return TaskCapabilities(
            can_stop=task.status == "running",
            can_remove=task.status != "running",
            has_logs=isinstance(log_buffer, list) and len(log_buffer) > 0,
            has_output=isinstance(print_buffer, list) and len(print_buffer) > 0,
        )

    def _get_friendly_target_name(self, target: str) -> str:
        if not target:
            return "LOCAL"
        if target.startswith("DESKTOP:"):
            try:
                parts = target.split(":")
                backend = parts[1] if len(parts) > 2 else ""
                handle_text = parts[2] if len(parts) > 2 else parts[-1]
                handle = int(handle_text) if handle_text.isdigit() else None
                for item in self.device_facade._desktop_raw:
                    item_handle = int(item.get("handle") or item.get("hwnd") or 0)
                    if handle is not None and item_handle == handle:
                        name = item.get("window_name")
                        if name:
                            return f"{current_desktop_label()}: {name}"
                if backend:
                    return f"{backend}:{handle_text}"
            except Exception:
                pass
        if target.startswith("ADB:"):
            try:
                address = target.split(":", 1)[1]
                for item in self.device_facade._adb_raw:
                    if item.get("address") == address:
                        name = item.get("name")
                        if name:
                            return f"设备: {name}"
            except Exception:
                pass
        return target

    def _build_task_name(self, task: TaskInfo) -> str:
        return str(task.title or task.summary.get("entry") or task.summary.get("script_path") or task.task_id)

    def _to_task_list_item_view(self, task: TaskInfo) -> TaskListItemView:
        return TaskListItemView(
            task_id=task.task_id,
            kind=task.kind,
            status=task.status,
            target=self._get_friendly_target_name(task.target),
            title=task.title,
            error=task.error,
            result=task.result,
            name=self._build_task_name(task),
            summary=self._build_task_summary(task),
            capabilities=self._build_task_capabilities(task),
        )

    def _to_task_detail_view(self, task: TaskInfo) -> TaskDetailView:
        return TaskDetailView(
            task_id=task.task_id,
            kind=task.kind,
            status=task.status,
            target=self._get_friendly_target_name(task.target),
            title=task.title,
            error=task.error,
            result=task.result,
            summary=self._build_task_summary(task),
            capabilities=self._build_task_capabilities(task),
        )

    def list_tasks(self) -> list[TaskInfo]:
        """获取当前任务列表"""
        return self.state_mgr.list_tasks()

    def list_task_views(self) -> list[TaskListItemView]:
        """获取面向前端/TUI 的任务列表视图"""
        return [self._to_task_list_item_view(task) for task in self.state_mgr.list_tasks()]

    def get_device_overview(self) -> DeviceOverview:
        """获取设备域通用状态"""
        return self.device_facade.get_overview()

    def get_task_info(self, task_id: str) -> TaskInfo | None:
        """查询特定任务执行情况"""
        return self.state_mgr.get_task(task_id)

    def get_task_detail_view(self, task_id: str) -> TaskDetailView | None:
        """获取任务详情只读视图"""
        task = self.state_mgr.get_task(task_id)
        if task is None:
            return None
        return self._to_task_detail_view(task)

    def get_task_logs(self, task_id: str) -> TaskLogsView | None:
        """获取任务日志只读视图"""
        task = self.state_mgr.get_task(task_id)
        if task is None:
            return None
        raw_items = task.log_buffer
        items = []
        if isinstance(raw_items, list):
            for item in raw_items:
                if isinstance(item, dict):
                    items.append(
                        TaskLogEntryView(
                            level=str(item.get("level") or "INFO").upper(),
                            message=str(item.get("message") or ""),
                        )
                    )
                else:
                    items.append(TaskLogEntryView(level="INFO", message=str(item)))
        return TaskLogsView(task_id=task_id, items=items)

    def get_task_output(self, task_id: str) -> TaskOutputView | None:
        """获取任务输出只读视图"""
        task = self.state_mgr.get_task(task_id)
        if task is None:
            return None
        raw_items = task.print_buffer
        items = [str(item) for item in raw_items] if isinstance(raw_items, list) else []
        max_lines = raw_items.max_lines if isinstance(raw_items, TaskOutputBuffer) else len(items) or 300
        total_lines = raw_items.total_lines if isinstance(raw_items, TaskOutputBuffer) else len(items)
        version = raw_items.version if isinstance(raw_items, TaskOutputBuffer) else 0
        return TaskOutputView(
            task_id=task_id,
            items=items,
            max_lines=max_lines,
            total_lines=total_lines,
            version=version,
        )

    def remove_task(self, task_id: str) -> bool:
        """删除任务记录"""
        return self.state_mgr.remove_task(task_id)

    def stop_all_tasks(self) -> int:
        """停止所有正在运行的任务，返回已停止的任务数"""
        tasks = self.list_task_views()
        stopped = 0
        for task in tasks:
            if not task.capabilities.can_stop:
                continue
            if task.kind == "script":
                self.stop_script(task.task_id)
            else:
                self.stop_pipeline(task.task_id)
            stopped += 1
        return stopped

    def run_last_task(self) -> str | None:
        """启动上一个任务"""
        if not hasattr(self, "_last_task_params") or not getattr(self, "_last_task_params"):
            return None
        
        last_params = getattr(self, "_last_task_params")
        kind = last_params.get("kind")
        params = last_params.get("params")
        if kind == "script":
            return self.run_script(**params)
        elif kind == "pipeline":
            return self.run_pipeline(**params)
        return None

    def run_script(self, script_path: str, code: str, target: str) -> str:
        """启动脚本并返回任务 ID"""
        self._last_task_params = {"kind": "script", "params": {"script_path": script_path, "code": code, "target": target}}
        return self.exec_mgr.start_script(script_path, code, target)

    def stop_script(self, task_id: str) -> None:
        """停止指定的脚本任务"""
        self.exec_mgr.stop_script(task_id)

    def run_pipeline(self, entry: str, override: dict[str, object] | None, target: str, project_path: str) -> str:
        """启动流水线并返回任务 ID"""
        self._last_task_params = {"kind": "pipeline", "params": {"entry": entry, "override": override, "target": target, "project_path": project_path}}
        return self.exec_mgr.start_pipeline(entry, override, target, project_path)

    def stop_pipeline(self, task_id: str) -> None:
        """停止流水线任务"""
        self.exec_mgr.stop_pipeline(task_id)

    def initialize_devices(self) -> DeviceActionResult:
        return self.device_facade.initialize()

    def refresh_devices(self) -> DeviceOverview:
        return self.device_facade.refresh()

    def find_adb_devices(self) -> DeviceActionResult:
        return self.device_facade.find_adb()

    def find_desktop_windows(self) -> DeviceActionResult:
        return self.device_facade.find_desktop()

    def change_adb_page(self, delta: int) -> DeviceOverview:
        return self.device_facade.change_adb_page(delta)

    def change_desktop_page(self, delta: int) -> DeviceOverview:
        return self.device_facade.change_desktop_page(delta)

    def connect_adb(self, address: str) -> DeviceActionResult:
        return self.device_facade.connect_adb(ConnectAdbRequest(address=address))

    def connect_device(self, action_id: str) -> DeviceActionResult:
        return self.device_facade.connect_device(action_id)

    def disconnect_device(self) -> DeviceActionResult:
        return self.device_facade.disconnect_device()

    def screencap_current_device(self) -> DeviceActionResult:
        return self.device_facade.screencap_current()

    def screencap_current_device_and_save(self) -> DeviceActionResult:
        return self.device_facade.screencap_current_and_save()


_global_control_facade = ControlFacade()


def get_control_facade() -> ControlFacade:
    return _global_control_facade
