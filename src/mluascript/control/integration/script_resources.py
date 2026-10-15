from __future__ import annotations

import atexit
from dataclasses import dataclass, replace
from pathlib import Path
from threading import Lock
from typing import Any

from mluascript.maa.controllers.base import controller_reconnect_pending
from mluascript.maa.lifecycle.bootstrap import resolve_maa_paths
from mluascript.maa.lifecycle.runtime import MaaContext, create_maa_context, initialize_maa_runtime
from mluascript.maa.types import MaaPaths
from mluascript.shared.logging import logger


@dataclass
class _IdleRuntime:
    controller: object | None
    signature: tuple
    resource: Any
    tasker: Any


# 只保留最近一次空闲实例，限制低内存主机上的模型常驻量；运行中的实例独占。
_idle: _IdleRuntime | None = None
_lock = Lock()


def _directory_signature(path: Path | None) -> tuple:
    if path is None:
        return ()
    root = path.resolve()
    items = []
    if root.exists():
        for item in sorted(root.rglob('*')):
            if item.is_file():
                stat = item.stat()
                items.append((item.relative_to(root).as_posix(), stat.st_size, stat.st_mtime_ns))
    return (str(root), tuple(items))


def _signature(paths: MaaPaths) -> tuple:
    return (str(paths.library_dir.resolve()), _directory_signature(paths.resource_dir), _directory_signature(paths.model_dir))


def acquire_script_maa_context(resource_dir: Path, controller: object | None) -> MaaContext:
    global _idle
    paths = replace(resolve_maa_paths(), resource_dir=Path(resource_dir))
    signature = _signature(paths)
    with _lock:
        idle, _idle = _idle, None
    if idle is not None and idle.controller is controller and idle.signature == signature:
        context = MaaContext(paths=paths, resource=idle.resource, tasker=idle.tasker)
        context.mark_loaded()
    else:
        idle = None
        context = create_maa_context()
        context.paths = paths
        initialize_maa_runtime(context)
    context.controller = controller
    context.state.extras['resource_signature'] = signature
    return context


def release_script_resources(context: MaaContext) -> bool:
    global _idle
    tasker, resource, controller = context.tasker, context.resource, context.controller
    if tasker is not None and (getattr(tasker, 'running', False) or getattr(tasker, 'stopping', False)):
        return False
    signature = context.state.extras.get('resource_signature')
    reusable = (
        tasker is not None and resource is not None and signature is not None
        and not context.state.extras.get('resource_dirty')
        and (controller is None or not controller_reconnect_pending(controller))
    )
    if reusable:
        try:
            reusable = signature == _signature(context.paths) and tasker.clear_cache()
        except Exception as exc:
            logger.warning(f'Maa runtime cannot be reused: {exc}')
            reusable = False
    if reusable:
        # 与 Maa Python Tasker.bind 的所有权规则保持一致，防止原生绑定先于持有者失效。
        tasker._resource_holder = resource
        tasker._controller_holder = controller
        with _lock:
            _idle = _IdleRuntime(controller, signature, resource, tasker)
    context.tasker = None
    context.resource = None
    context.controller = None
    context.state.extras.clear()
    context.mark_connected(None)
    return True


def clear_idle_script_runtime() -> None:
    global _idle
    with _lock:
        _idle = None


atexit.register(clear_idle_script_runtime)
