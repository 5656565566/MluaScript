from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TaskRequest:
    entry: str
    override: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TaskResult:
    succeeded: bool
    detail: Any = None
