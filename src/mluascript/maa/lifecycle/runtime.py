from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker
from maa.controller import Controller
from maa.toolkit import Toolkit

from mluascript.shared.logging import logger
from mluascript.shared.config.manager import get_runtime_dir

from ..types import MaaContextState, MaaPaths
from .bootstrap import resolve_maa_log_dir, resolve_maa_log_file, resolve_maa_paths, resolve_tasker_stdout_level


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

        try:
            if Tasker.set_log_dir(maa_log_dir):
                _stabilize_maa_log_file(maa_log_file)
                logger.info(f"MAA 底层日志已启用: {maa_log_file}")
            else:
                logger.warning(f"MAA 底层日志目录设置失败: {maa_log_dir}")
        except Exception as exc:
            logger.error(f"MAA 底层日志启用失败: {exc}")

        try:
            Tasker.set_stdout_level(resolve_tasker_stdout_level())
            _stabilize_maa_log_file(maa_log_file)
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

    option_data["logging"] = True
    option_data["stdout_level"] = 0
    option_path.write_text(json.dumps(option_data, ensure_ascii=False, indent=4), encoding="utf-8")


def _stabilize_maa_log_file(target_file: Path, runtime_dir: Path | None = None) -> None:
    target_runtime_dir = runtime_dir or get_runtime_dir()
    root_generated_file = target_runtime_dir / "maafw.log"
    debug_generated_file = target_runtime_dir / "debug" / "maafw.log"
    generated_file = target_file.parent / "maafw.log"
    target_file.parent.mkdir(parents=True, exist_ok=True)

    for candidate in (root_generated_file, debug_generated_file):
        if not candidate.exists():
            continue
        try:
            current = target_file.read_bytes() if target_file.exists() else b""
            incoming = candidate.read_bytes()
            if incoming:
                target_file.write_bytes(current + incoming)
            candidate.unlink()
        except Exception:
            pass

    if generated_file == target_file or not generated_file.exists():
        _cleanup_maa_debug_dir(target_runtime_dir)
        return

    if target_file.exists():
        try:
            existing = target_file.read_bytes()
            current = generated_file.read_bytes()
            generated_file.write_bytes(existing + current)
            target_file.unlink()
        except Exception:
            try:
                target_file.unlink()
            except Exception:
                return

    try:
        generated_file.replace(target_file)
        _cleanup_maa_debug_dir(target_runtime_dir)
        return
    except Exception:
        pass

    try:
        os.link(generated_file, target_file)
    except Exception:
        pass
    _cleanup_maa_debug_dir(target_runtime_dir)


def _cleanup_maa_debug_dir(runtime_dir: Path | None = None) -> None:
    debug_dir = (runtime_dir or get_runtime_dir()) / "debug"
    try:
        if debug_dir.exists() and not any(debug_dir.iterdir()):
            debug_dir.rmdir()
    except Exception:
        pass


def cleanup_maa_runtime_artifacts(runtime_dir: Path | None = None) -> None:
    target_runtime_dir = runtime_dir or get_runtime_dir()
    maa_log_file = resolve_maa_log_file(target_runtime_dir)
    _stabilize_maa_log_file(maa_log_file, target_runtime_dir)
