"""MluaScript 共享日志基础设施"""
from __future__ import annotations

import inspect
import logging
import sys
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Any, Callable

import loguru

if TYPE_CHECKING:
    from loguru import Logger, Message, Record
    from textual.widgets import RichLog

logger: Logger = loguru.logger
log_level = "INFO"
logger_id: int | None = None
_DEFAULT_BUFFER_LIMIT = 2000
_DEFAULT_BUCKET_LIMIT = 500
_sink_ids: dict[str, int] = {}
_stdout_enabled = False
_file_log_dir: Path | None = None


@dataclass(slots=True)
class LogEntry:
    timestamp: str
    level: str
    source: str
    session_label: str
    channel: str
    message: str
    formatted: str
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "level": self.level,
            "source": self.source,
            "session_label": self.session_label,
            "channel": self.channel,
            "message": self.message,
            "formatted": self.formatted,
            "extra": dict(self.extra),
        }


class LogBufferManager:
    """统一日志缓冲区管理器"""

    def __init__(self, *, maxlen: int = _DEFAULT_BUFFER_LIMIT, bucket_maxlen: int = _DEFAULT_BUCKET_LIMIT) -> None:
        self.maxlen = maxlen
        self.bucket_maxlen = bucket_maxlen
        self._lock = Lock()
        self._all: deque[LogEntry] = deque(maxlen=maxlen)
        self._by_session: dict[str, deque[LogEntry]] = {}
        self._by_channel: dict[str, deque[LogEntry]] = {}

    def clear(self) -> None:
        with self._lock:
            self._all.clear()
            self._by_session.clear()
            self._by_channel.clear()

    def append(self, entry: LogEntry) -> None:
        with self._lock:
            self._all.append(entry)
            self._get_session_buffer(entry.session_label).append(entry)
            self._get_channel_buffer(entry.channel).append(entry)

    def _get_session_buffer(self, session_label: str) -> deque[LogEntry]:
        if session_label not in self._by_session:
            self._by_session[session_label] = deque(maxlen=self.bucket_maxlen)
        return self._by_session[session_label]

    def _get_channel_buffer(self, channel: str) -> deque[LogEntry]:
        if channel not in self._by_channel:
            self._by_channel[channel] = deque(maxlen=self.bucket_maxlen)
        return self._by_channel[channel]

    def list_all(self, limit: int | None = None) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._all)
        if limit is not None:
            items = items[-limit:]
        return [item.to_dict() for item in items]

    def list_by_session(self, session_label: str, limit: int | None = None) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._by_session.get(session_label, ()))
        if limit is not None:
            items = items[-limit:]
        return [item.to_dict() for item in items]

    def list_by_channel(self, channel: str, limit: int | None = None) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._by_channel.get(channel, ()))
        if limit is not None:
            items = items[-limit:]
        return [item.to_dict() for item in items]

    def iter_sessions(self) -> list[str]:
        with self._lock:
            return list(self._by_session.keys())


class BufferedLogSink:
    def __init__(self, buffer_manager: LogBufferManager) -> None:
        self.buffer_manager = buffer_manager

    def write(self, message: Message) -> None:
        record = message.record
        source = str(record["extra"].get("source", "system"))
        session_label = str(record["extra"].get("session_label", "system"))
        channel = str(record["extra"].get("channel", "default"))
        formatted = str(message).rstrip("\n")
        extra = {k: v for k, v in record["extra"].items() if k not in {"source", "session_label", "channel"}}
        entry = LogEntry(
            timestamp=record["time"].strftime("%m-%d %H:%M:%S"),
            level=str(record["level"].name),
            source=source,
            session_label=session_label,
            channel=channel,
            message=str(record["message"]),
            formatted=formatted,
            extra=extra,
        )
        self.buffer_manager.append(entry)


class TuiLogSink:
    def __init__(self) -> None:
        self._target: RichLog | None = None

    def bind_target(self, target: RichLog | None) -> None:
        self._target = target

    def write(self, message: Message) -> None:
        if self._target is None:
            return
        text = str(message).rstrip("\n")
        try:
            if self._target.is_attached:
                from rich.text import Text

                self._target.app.call_from_thread(self._target.write, Text.from_ansi(text))
        except Exception:
            pass


log_buffer_manager = LogBufferManager()
_buffer_sink = BufferedLogSink(log_buffer_manager)
_tui_sink = TuiLogSink()


class LoguruHandler(logging.Handler):
    """logging 与 loguru 之间的桥梁 将 logging 日志转发到 loguru"""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = inspect.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())



def set_log_level(level: str) -> None:
    global log_level
    log_level = level



def default_filter(record: "Record") -> bool:
    levelno = logger.level(log_level).no if isinstance(log_level, str) else log_level
    return record["level"].no >= levelno



def runtime_filter(record: "Record") -> bool:
    return str(record["extra"].get("channel", "")) == "runtime.log"



def runtime_output_filter(record: "Record") -> bool:
    return str(record["extra"].get("channel", "")) == "runtime.output"



default_format: str = (
    "<g>{time:MM-DD HH:mm:ss}</g> "
    "[<lvl>{level}</lvl>] "
    "<c><u>{module}</u></c> | "
    "{message}"
)
"""默认日志格式"""


logger.remove()



def register_sink(
    name: str,
    target: Any,
    *,
    level: int | str = 0,
    filter: Callable[[Record], bool] | None = None,
    format: str | None = None,
    diagnose: bool = False,
    colorize: bool | None = None,
) -> int:
    if name in _sink_ids:
        logger.remove(_sink_ids.pop(name))
    sink_id = logger.add(
        target,
        level=level,
        filter=filter or default_filter,
        format=format or default_format,
        diagnose=diagnose,
        colorize=colorize,
    )
    _sink_ids[name] = sink_id
    return sink_id



def remove_sink(name: str) -> None:
    sink_id = _sink_ids.pop(name, None)
    if sink_id is not None:
        logger.remove(sink_id)



def has_sink(name: str) -> bool:
    return name in _sink_ids



def ensure_buffer_sink() -> None:
    if not has_sink("buffer"):
        register_sink("buffer", _buffer_sink, colorize=True)



def enable_stdout_sink() -> None:
    global _stdout_enabled, logger_id
    ensure_buffer_sink()
    register_sink("stdout", sys.stdout)
    _stdout_enabled = True
    logger_id = _sink_ids.get("stdout")


def configure_file_logging(log_dir: Path | str | None) -> None:
    global _file_log_dir
    if not log_dir:
        remove_sink("file")
        _file_log_dir = None
        return

    target_dir = Path(log_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    register_sink(
        "file",
        str(target_dir / "mluascript.log"),
        level=0,
        diagnose=False,
        colorize=False,
    )
    _file_log_dir = target_dir



def disable_stdout_sink() -> None:
    global _stdout_enabled, logger_id
    remove_sink("stdout")
    _stdout_enabled = False
    logger_id = None



def register_tui_sink(target: RichLog | None = None) -> None:
    ensure_buffer_sink()
    _tui_sink.bind_target(target)
    register_sink("tui", _tui_sink, colorize=True)



def bind_tui_log_target(target: RichLog | None) -> None:
    _tui_sink.bind_target(target)



def clear_log_buffers() -> None:
    log_buffer_manager.clear()



def get_logs(limit: int | None = None) -> list[dict[str, Any]]:
    return log_buffer_manager.list_all(limit=limit)



def get_logs_by_session(session_label: str, limit: int | None = None) -> list[dict[str, Any]]:
    return log_buffer_manager.list_by_session(session_label, limit=limit)



def get_logs_by_channel(channel: str, limit: int | None = None) -> list[dict[str, Any]]:
    return log_buffer_manager.list_by_channel(channel, limit=limit)



def iter_log_sessions() -> list[str]:
    return log_buffer_manager.iter_sessions()



def build_log_lines(items: list[dict[str, Any]]) -> list[str]:
    return [str(item.get("formatted") or item.get("message") or "") for item in items]



def get_runtime_logs(run_id: str, limit: int | None = None) -> list[dict[str, Any]]:
    items = get_logs_by_session(run_id, limit=limit)
    return [item for item in items if item.get("channel") == "runtime.log"]



def get_runtime_output(run_id: str, limit: int | None = None) -> list[dict[str, Any]]:
    items = get_logs_by_session(run_id, limit=limit)
    return [item for item in items if item.get("channel") == "runtime.output"]



def build_runtime_output_lines(items: list[dict[str, Any]]) -> list[str]:
    return [str(item.get("message") or "") for item in items]



def configure_logging(*, stdout: bool = True) -> None:
    ensure_buffer_sink()
    if stdout:
        enable_stdout_sink()
    else:
        disable_stdout_sink()
    if _file_log_dir is not None:
        configure_file_logging(_file_log_dir)


configure_logging(stdout=True)
logger_id = _sink_ids.get("stdout")
"""默认日志处理器 id"""
