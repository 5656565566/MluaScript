from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RecognitionResult:
    """统一识别结果模型"""

    hit: bool = False
    entry: str = ""
    name: str | None = None
    box: list[int | float | str] | None = None
    score: float | int | None = None
    text: str | None = None
    results: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self, include_results: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "hit": self.hit,
            "entry": self.entry,
        }
        if self.name is not None:
            data["name"] = self.name
        if self.box is not None:
            data["box"] = self.box
        if self.score is not None:
            data["score"] = self.score
        if self.text is not None:
            data["text"] = self.text
        if include_results:
            data["results"] = list(self.results)
        return data
