from __future__ import annotations

from typing import Any


def build_pipeline_override(entry: str, node_override: dict[str, Any] | None = None) -> dict[str, Any]:
    if not node_override:
        return {}
    return {entry: node_override}
