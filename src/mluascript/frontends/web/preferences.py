"""Web 界面偏好模型与持久化服务。"""

from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mluascript.shared.logging import logger


class _PreferenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class AppearancePreferences(_PreferenceModel):
    theme_mode: Literal["system", "light", "dark"] = Field(default="system", alias="themeMode")
    color_theme: Literal["classic", "emerald", "blue", "violet", "amber", "red", "cyan", "custom"] = Field(
        default="classic",
        alias="colorTheme",
    )
    custom_color: str = Field(default="#18a058", alias="customColor", pattern=r"^#[0-9a-fA-F]{6}$")
    palette_version: Literal[1] = Field(default=1, alias="paletteVersion")
    legacy_accent_color: str | None = Field(
        default=None,
        alias="accentColor",
        pattern=r"^#[0-9a-fA-F]{6}$",
        exclude=True,
    )

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_accent_color(cls, value: object) -> object:
        """旧版单色强调配置迁移为自定义种子色，避免覆盖用户选择。"""

        if not isinstance(value, dict) or "accentColor" not in value or "colorTheme" in value:
            return value
        migrated = dict(value)
        migrated["colorTheme"] = "custom"
        migrated["customColor"] = migrated["accentColor"]
        return migrated


class EditorPreferences(_PreferenceModel):
    auto_save_files: bool = Field(default=True, alias="autoSaveFiles")
    project_tree_visible: bool = Field(default=True, alias="projectTreeVisible")
    project_tree_width: int = Field(default=240, alias="projectTreeWidth", ge=200, le=420)


class TaskPreferences(_PreferenceModel):
    auto_refresh: bool = Field(default=True, alias="autoRefresh")
    active_tab: str = Field(default="resource-list", alias="activeTab", max_length=64)


class LogPreferences(_PreferenceModel):
    auto_scroll: bool = Field(default=True, alias="autoScroll")
    selected_level: str = Field(default="all", alias="selectedLevel", max_length=32)
    origin: str = Field(default="runtime", max_length=64)


class LayoutPreferences(_PreferenceModel):
    sidebar_collapsed: bool = Field(default=False, alias="sidebarCollapsed")
    active_view: str = Field(default="editor", alias="activeView", max_length=64)


class WebPreferences(_PreferenceModel):
    appearance: AppearancePreferences = Field(default_factory=AppearancePreferences)
    editor: EditorPreferences = Field(default_factory=EditorPreferences)
    tasks: TaskPreferences = Field(default_factory=TaskPreferences)
    logs: LogPreferences = Field(default_factory=LogPreferences)
    layout: LayoutPreferences = Field(default_factory=LayoutPreferences)


class _PreferenceDocument(_PreferenceModel):
    schema_version: int = Field(default=1, alias="schemaVersion")
    users: dict[str, WebPreferences] = Field(default_factory=dict)


class WebPreferenceService:
    """按登录用户名保存界面偏好，并使用原子替换避免半写文件。"""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).resolve()
        self._lock = RLock()

    def _read_document(self) -> _PreferenceDocument:
        if not self.path.exists():
            return _PreferenceDocument()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return _PreferenceDocument.model_validate(raw)
        except (OSError, ValueError) as exc:
            logger.warning(f"读取 Web 偏好设置失败，使用默认值: {exc}")
            return _PreferenceDocument()

    def get(self, username: str) -> WebPreferences:
        with self._lock:
            document = self._read_document()
            return document.users.get(username, WebPreferences()).model_copy(deep=True)

    def put(self, username: str, preferences: WebPreferences) -> WebPreferences:
        with self._lock:
            document = self._read_document()
            document.users[username] = preferences.model_copy(deep=True)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.parent / f".{self.path.name}.{uuid4().hex}.tmp"
            try:
                temporary.write_text(
                    json.dumps(document.model_dump(by_alias=True), ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                temporary.replace(self.path)
            finally:
                if temporary.exists():
                    temporary.unlink()
            return preferences.model_copy(deep=True)
