from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class ScriptInfo(BaseModel):
    """表示一个工作区脚本文件的信息"""

    name: str
    path: str
    mtime: float


class WorkspaceProject(BaseModel):
    """表示一个可运行脚本项目的根布局"""

    project_id: str
    name: str
    root_dir: str
    scripts_dir: str
    resource_dir: str
    templates_dir: str | None = None
    config_file: str | None = None


class ScriptAsset(BaseModel):
    """表示项目内的脚本资产"""

    project_id: str
    name: str
    relative_path: str
    absolute_path: str
    mtime: float
    is_entry: bool = True


class ResourceAsset(BaseModel):
    """表示项目内的资源资产"""

    project_id: str
    relative_path: str
    absolute_path: str
    kind: str


class ScriptRunLocator(BaseModel):
    """脚本运行所需的项目/脚本/资源定位信息"""

    project: WorkspaceProject
    script: ScriptAsset
    project_root: str
    script_file: str
    script_dir: str
    working_dir: str
    resource_dir: str
    templates_dir: str | None = None
    resources: list[ResourceAsset] = Field(default_factory=list)


class PipelineRunLocator(BaseModel):
    """pipeline 运行所需的项目/资源定位信息"""

    project: WorkspaceProject
    project_root: str
    working_dir: str
    resource_dir: str
    templates_dir: str | None = None
    resources: list[ResourceAsset] = Field(default_factory=list)


def path_to_str(path: Path) -> str:
    return str(path.resolve())
