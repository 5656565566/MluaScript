from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, Lock, Thread

from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker
from maa.controller import Controller
from maa.toolkit import Toolkit

from mluascript.shared.logging import logger
from mluascript.shared.config.manager import get_runtime_dir

from ..types import MaaContextState, MaaPaths
from .bootstrap import resolve_maa_log_dir, resolve_maa_log_file, resolve_maa_paths, resolve_tasker_stdout_level


_MAA_LOG_FILENAME = "maafw.log"
_MAA_LOG_BACKUP_PATTERN = "maafw.bak.*.log"
_MAA_LOG_BACKUP_LIMIT = 5
_MAA_LOG_MAINTENANCE_INTERVAL_SECONDS = 60
_maa_log_maintenance_lock = Lock()
_maa_log_maintenance_stop = Event()
_maa_log_maintenance_thread: Thread | None = None
_maa_log_maintenance_dir: Path | None = None


@dataclass(slots=True)
class MaaContext:
    """Maa 核运行上下文"""

    paths: MaaPaths
    state: MaaContextState = field(default_factory=MaaContextState)
    library: Library | None = None
    resource: Resource | None = None
    tasker: Tasker | None = None
    controller: Controller | None = None

    def mark_loaded(self) -> None:
        self.state.loaded = True
        logger.debug(f"Maa context loaded: library_dir={self.paths.library_dir}")

    def mark_connected(self, label: str | None) -> None:
        self.state.connected = label is not None
        self.state.connection_label = label



def create_maa_context() -> MaaContext:
    """创建最小 Maa 上下文 不立即触发实际库加载"""
    runtime_dir = get_runtime_dir()
    maa_log_file = resolve_maa_log_file(runtime_dir)
    _prepare_maa_option_config(runtime_dir)
    maa_log_dir = maa_log_file.parent
    maa_log_dir.mkdir(parents=True, exist_ok=True)

    with _redirect_native_stdio(maa_log_file):
        try:
            Toolkit.init_option(str(runtime_dir))
        except Exception as exc:
            logger.error(f"Failed to init Toolkit option: {exc}")

        # Toolkit 配置阶段关闭临时日志，先归拢旧文件，再只在目标目录启动 MAA 日志。
        _stabilize_maa_log_file(maa_log_file, runtime_dir)

        try:
            if Tasker.set_log_dir(maa_log_dir):
                _prune_maa_log_backups(maa_log_dir)
                _ensure_maa_log_maintenance(maa_log_dir)
                logger.info(f"MAA 底层日志已启用: {maa_log_file}")
            else:
                logger.warning(f"MAA 底层日志目录设置失败: {maa_log_dir}")
        except Exception as exc:
            logger.error(f"MAA 底层日志启用失败: {exc}")

        try:
            Tasker.set_stdout_level(resolve_tasker_stdout_level())
        except Exception as exc:
            logger.error(f"MAA stdout 日志级别设置失败: {exc}")
    return MaaContext(paths=resolve_maa_paths())



def initialize_maa_runtime(context: MaaContext) -> MaaContext:
    """按需初始化真实 Maa 运行时组件"""
    if context.tasker is not None and context.resource is not None:
        return context

    maa_log_file = resolve_maa_log_file(get_runtime_dir())

    with _redirect_native_stdio(maa_log_file):
        try:
            Library.open(context.paths.library_dir)
        except Exception:
            pass

        if context.resource is None:
            try:
                context.resource = Resource()
            except Exception as exc:
                logger.error(f"Maa resource 初始化失败: {exc}")
                context.resource = None

        if context.tasker is None:
            try:
                context.tasker = Tasker()
            except Exception as exc:
                logger.error(f"Maa tasker 初始化失败: {exc}")
                context.tasker = None

        if context.tasker is not None and context.resource is not None:
            try:
                bind_resource = getattr(Library.framework(), "MaaTaskerBindResource", None)
                if bind_resource is not None:
                    bind_resource(context.tasker._handle, context.resource._handle)
            except Exception as exc:
                logger.error(f"Maa tasker 绑定 resource 失败: {exc}")

        if context.resource is not None:
            if context.paths.model_dir is None:
                logger.warning("Maa OCR 模型未配置: model_dir is None")
            else:
                ocr_model_dir = context.paths.model_dir / "ocr"
                if ocr_model_dir.exists():
                    try:
                        logger.info(f"加载 Maa OCR 模型目录: {ocr_model_dir}")
                        context.resource.post_ocr_model(ocr_model_dir).wait()
                    except Exception as exc:
                        logger.error(f"Maa OCR 模型加载失败: {exc}")
                else:
                    logger.warning(f"Maa OCR 模型目录不存在: {ocr_model_dir}")

    context.mark_loaded()
    return context


@contextmanager
def _redirect_native_stdio(target_file: Path):
    if os.name == "nt":
        yield
        return

    target_file.parent.mkdir(parents=True, exist_ok=True)
    saved_stdout_fd = None
    saved_stderr_fd = None
    stream = None
    try:
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass

        saved_stdout_fd = os.dup(1)
        saved_stderr_fd = os.dup(2)
        stream = open(target_file, "ab", buffering=0)
        os.dup2(stream.fileno(), 1)
        os.dup2(stream.fileno(), 2)
        yield
    finally:
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass

        if saved_stdout_fd is not None:
            os.dup2(saved_stdout_fd, 1)
            os.close(saved_stdout_fd)
        if saved_stderr_fd is not None:
            os.dup2(saved_stderr_fd, 2)
            os.close(saved_stderr_fd)
        if stream is not None:
            stream.close()


def _prepare_maa_option_config(runtime_dir: Path) -> None:
    config_dir = runtime_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    option_path = config_dir / "maa_option.json"

    option_data: dict[str, object] = {}
    if option_path.exists():
        try:
            loaded = json.loads(option_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                option_data = loaded
        except Exception:
            option_data = {}

    # MAA 日志目录由 Tasker.set_log_dir 统一设置，避免 Toolkit 先在 debug 或工作目录落盘。
    option_data["logging"] = False
    option_data["stdout_level"] = 0
    option_path.write_text(json.dumps(option_data, ensure_ascii=False, indent=4), encoding="utf-8")


def _stabilize_maa_log_file(target_file: Path, runtime_dir: Path | None = None) -> None:
    target_runtime_dir = runtime_dir or get_runtime_dir()
    target_dir = target_file.parent
    native_log_file = target_dir / _MAA_LOG_FILENAME
    target_dir.mkdir(parents=True, exist_ok=True)

    # 只归拢 MAA 自身的固定文件名，避免处理程序根目录中的其他日志。
    for source_dir in (target_runtime_dir, target_runtime_dir / "debug"):
        source_log_file = source_dir / _MAA_LOG_FILENAME
        if source_log_file != native_log_file:
            _merge_maa_log_file(source_log_file, native_log_file)
        for backup_file in source_dir.glob(_MAA_LOG_BACKUP_PATTERN):
            _move_maa_backup_file(backup_file, target_dir)

    _prune_maa_log_backups(target_dir)
    _cleanup_maa_debug_dir(target_runtime_dir)


def _merge_maa_log_file(source_file: Path, target_file: Path) -> None:
    if not source_file.is_file():
        return
    try:
        incoming = source_file.read_bytes()
        if incoming:
            with target_file.open("ab") as stream:
                stream.write(incoming)
        source_file.unlink()
    except OSError:
        pass


def _move_maa_backup_file(source_file: Path, target_dir: Path) -> None:
    if not source_file.is_file() or source_file.parent == target_dir:
        return
    destination = target_dir / source_file.name
    suffix_index = 1
    while destination.exists():
        destination = target_dir / f"{source_file.stem}.migrated-{suffix_index}{source_file.suffix}"
        suffix_index += 1
    try:
        source_file.replace(destination)
    except OSError:
        pass


def _prune_maa_log_backups(log_dir: Path, keep: int = _MAA_LOG_BACKUP_LIMIT) -> None:
    try:
        backups = sorted(
            (item for item in log_dir.glob(_MAA_LOG_BACKUP_PATTERN) if item.is_file()),
            key=lambda item: item.stat().st_mtime_ns,
            reverse=True,
        )
    except OSError:
        return

    for backup_file in backups[max(0, keep):]:
        try:
            backup_file.unlink()
        except OSError:
            pass


def _ensure_maa_log_maintenance(log_dir: Path) -> None:
    global _maa_log_maintenance_dir, _maa_log_maintenance_thread
    with _maa_log_maintenance_lock:
        _maa_log_maintenance_dir = log_dir.resolve()
        if _maa_log_maintenance_thread is not None and _maa_log_maintenance_thread.is_alive():
            return
        _maa_log_maintenance_stop.clear()
        _maa_log_maintenance_thread = Thread(
            target=_run_maa_log_maintenance,
            name="maa-log-maintenance",
            daemon=True,
        )
        _maa_log_maintenance_thread.start()


def _run_maa_log_maintenance() -> None:
    while not _maa_log_maintenance_stop.wait(_MAA_LOG_MAINTENANCE_INTERVAL_SECONDS):
        with _maa_log_maintenance_lock:
            log_dir = _maa_log_maintenance_dir
        if log_dir is not None:
            _prune_maa_log_backups(log_dir)


def _stop_maa_log_maintenance() -> None:
    global _maa_log_maintenance_dir, _maa_log_maintenance_thread
    with _maa_log_maintenance_lock:
        thread = _maa_log_maintenance_thread
        _maa_log_maintenance_stop.set()
    if thread is not None and thread.is_alive():
        thread.join(timeout=1)
    with _maa_log_maintenance_lock:
        _maa_log_maintenance_dir = None
        _maa_log_maintenance_thread = None


def _cleanup_maa_debug_dir(runtime_dir: Path | None = None) -> None:
    debug_dir = (runtime_dir or get_runtime_dir()) / "debug"
    try:
        if debug_dir.exists() and not any(debug_dir.iterdir()):
            debug_dir.rmdir()
    except Exception:
        pass


def cleanup_maa_runtime_artifacts(runtime_dir: Path | None = None) -> None:
    _stop_maa_log_maintenance()
    target_runtime_dir = runtime_dir or get_runtime_dir()
    maa_log_file = resolve_maa_log_file(target_runtime_dir)
    _stabilize_maa_log_file(maa_log_file, target_runtime_dir)
