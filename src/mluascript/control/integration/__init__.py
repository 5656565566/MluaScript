from __future__ import annotations

"""
临时实现说明：
当前 [`src/mluascript/integration/`](src/mluascript/integration) 仅作为过渡期目录存在。
长期目标是将本包整体回收至 `src/mluascript/control/integration/`，
因此这里的导出仅用于当前重构阶段维持最小可用骨架。
"""

from .facade import IntegrationFacade
from .models import MaaPipelineRunContext, ScriptRunContext

__all__ = [
    "IntegrationFacade",
    "MaaPipelineRunContext",
    "ScriptRunContext",
]
