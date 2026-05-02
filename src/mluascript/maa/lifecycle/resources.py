from __future__ import annotations

from typing import Any

from mluascript.shared.logging import logger

from ..errors import MaaResourceError
from .runtime import MaaContext


def load_resource(context: MaaContext, path: str | None = None) -> bool:
    """加载 Maa 资源目录"""
    target = path or str(context.paths.resource_dir)
    if context.resource is None:
        logger.debug(f"Maa resource placeholder prepared: {target}")
        return True
    try:
        context.resource.post_bundle(target).wait()
        return True
    except Exception as exc:
        raise MaaResourceError(f"Failed to load resource: {target}") from exc


def override_pipeline(context: MaaContext, override: dict[str, Any]) -> bool:
    """覆盖 pipeline 配置"""
    if context.resource is None:
        logger.debug("Maa resource not initialized, skip override pipeline")
        return False
    return bool(context.resource.override_pipeline(override))


def get_node_list(context: MaaContext) -> list[str]:
    """获取当前资源节点列表"""
    if context.resource is None:
        return []
    try:
        return list(context.resource.node_list)
    except Exception:
        return []
