from __future__ import annotations

from dataclasses import dataclass, field

from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker
from maa.controller import Controller
from maa.toolkit import Toolkit

from mluascript.shared.logging import logger
from mluascript.shared.config.manager import get_runtime_dir

from ..types import MaaContextState, MaaPaths
from .bootstrap import resolve_maa_paths, resolve_tasker_stdout_level


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
    try:
        Toolkit.init_option(str(get_runtime_dir()))
    except Exception as exc:
        logger.error(f"Failed to init Toolkit option: {exc}")
    
    Tasker.set_stdout_level(resolve_tasker_stdout_level())
    return MaaContext(paths=resolve_maa_paths())



def initialize_maa_runtime(context: MaaContext) -> MaaContext:
    """按需初始化真实 Maa 运行时组件"""
    if context.tasker is not None and context.resource is not None:
        return context

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
