from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

TaskKind = Literal["script", "pipeline"]
TaskStatus = Literal["pending", "running", "success", "failed", "stopped"]


class TaskCapabilities(BaseModel):
    """任务可执行动作与可读取内容摘要"""

    can_stop: bool = False
    can_remove: bool = False
    has_logs: bool = False
    has_output: bool = False


class TaskInfo(BaseModel):
    """表示一个正在运行或历史的执行任务信息"""

    task_id: str
    kind: TaskKind
    status: TaskStatus
    target: str  # 关联的目标设备/会话 label 或文件路径
    title: str | None = None
    error: str | None = None
    result: Any | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    log_buffer: list[Any] = Field(default_factory=list)
    print_buffer: list[Any] = Field(default_factory=list)
    capabilities: TaskCapabilities = Field(default_factory=TaskCapabilities)


class TaskListItemView(BaseModel):
    """供前端/TUI 列表展示的任务只读视图"""

    task_id: str
    kind: TaskKind
    status: TaskStatus
    target: str
    title: str | None = None
    error: str | None = None
    result: Any | None = None
    name: str
    summary: dict[str, Any] = Field(default_factory=dict)
    capabilities: TaskCapabilities = Field(default_factory=TaskCapabilities)


class TaskDetailView(BaseModel):
    """供前端/TUI 详情展示的任务只读视图"""

    task_id: str
    kind: TaskKind
    status: TaskStatus
    target: str
    title: str | None = None
    error: str | None = None
    result: Any | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    capabilities: TaskCapabilities = Field(default_factory=TaskCapabilities)


class TaskLogEntryView(BaseModel):
    """任务日志条目视图"""

    level: str = "INFO"
    message: str = ""


class TaskLogsView(BaseModel):
    """任务日志视图"""

    task_id: str
    items: list[TaskLogEntryView] = Field(default_factory=list)


class TaskOutputView(BaseModel):
    """任务输出视图"""

    task_id: str
    items: list[str] = Field(default_factory=list)
    max_lines: int = 300
    total_lines: int = 0
    version: int = 0


class SystemState(BaseModel):
    """当前应用级的全局系统状态"""

    active_tasks: list[TaskInfo] = Field(default_factory=list)
    connected_sessions: list[str] = Field(default_factory=list)
