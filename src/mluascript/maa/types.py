from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class MaaPaths:
    """Maa 运行所需路径集合"""

    library_dir: Path
    resource_dir: Path
    model_dir: Path | None = None
    adb_path: Path | None = None


@dataclass(slots=True)
class MaaContextState:
    """Maa 上下文的可变运行状态"""

    loaded: bool = False
    connected: bool = False
    connection_label: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)
