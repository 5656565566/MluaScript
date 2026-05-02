from __future__ import annotations

from .base import MaaController, SupportsShape, ensure_controller
from .screen import screencap
from ..lifecycle.runtime import MaaContext


def get_resolution(context: MaaContext) -> tuple[int, int]:
    controller: MaaController = ensure_controller(context)
    resolution = controller.resolution
    if len(resolution) >= 2:
        return int(resolution[0]), int(resolution[1])

    image: SupportsShape | None = screencap(context)
    if image is None:
        raise RuntimeError("Failed to get device resolution")
    shape = image.shape
    return int(shape[1]), int(shape[0])


def get_uuid(context: MaaContext) -> str:
    controller: MaaController = ensure_controller(context)
    return controller.uuid


def get_connection_label(context: MaaContext) -> str:
    return context.state.connection_label or "未连接"
