"""项目包 v1 的数据模型。

项目目录和 `.mlspkg` 使用同一份 manifest 描述。模型保持在 workspace
包内，避免 Web 层重新定义一套容易漂移的项目契约。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProjectPackageMetadata(BaseModel):
    """项目身份信息。"""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    author: str = ""
    description: str = ""


class ProjectRuntimeSpec(BaseModel):
    """项目运行时约束。"""

    model_config = ConfigDict(extra="forbid")

    lua: str = "5.4"
    mluascript: str = ">=1.0.0"


class ProjectEntrypoint(BaseModel):
    """一个可执行入口以及它关联的编辑器/模型文件。"""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    script: str | None = Field(default=None, min_length=1)
    blockly: str | None = None
    maa: str | None = None
    template: str | None = None
    models: dict[str, str] = Field(default_factory=dict)


class ProjectModelSpec(BaseModel):
    """包内模型声明。v1 不允许外部下载。"""

    model_config = ConfigDict(extra="forbid")

    type: str = Field(min_length=1)
    path: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectManifest(BaseModel):
    """`mluascript.yaml` 的 v1 结构。"""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_: str = Field(default="mluascript.package/v1", alias="schema")
    project_type: str = Field(default="lua-package", alias="type")
    package: ProjectPackageMetadata
    runtime: ProjectRuntimeSpec = Field(default_factory=ProjectRuntimeSpec)
    entrypoints: dict[str, ProjectEntrypoint] = Field(default_factory=dict)
    resources: dict[str, str] = Field(default_factory=dict)
    models: dict[str, ProjectModelSpec] = Field(default_factory=dict)
    capabilities: dict[str, bool | str] = Field(default_factory=dict)
    extensions: dict[str, Any] = Field(default_factory=dict)


class ProjectDiagnostic(BaseModel):
    """manifest 或项目文件的结构化诊断。"""

    severity: str = "error"
    code: str
    message: str
    path: str | None = None


class ProjectSummary(BaseModel):
    """前端项目列表和打开项目使用的摘要。"""

    key: str
    name: str
    package_id: str
    version: str
    author: str = ""
    description: str = ""
    directory: str
    project_type: str = "lua-package"
    buildable: bool = True
    primary_path: str = ""
    valid: bool
    entrypoints: list[str] = Field(default_factory=list)
    model_count: int = 0
    file_count: int = 0
    diagnostics: list[ProjectDiagnostic] = Field(default_factory=list)


class ProjectTreeItem(BaseModel):
    """项目树中的一个文件或目录。"""

    path: str
    name: str
    kind: str
    size: int = 0
    mtime: float | None = None


class ProjectFileContent(BaseModel):
    """项目文件读取结果。"""

    path: str
    name: str
    size: int
    mtime: float
    encoding: str | None = "utf-8"
    content: str | None = None


class ProjectBuildResult(BaseModel):
    """一次打包构建的结果。"""

    build_id: str
    project_key: str
    filename: str
    artifact_path: str
    size: int
    sha256: str
    files: list[str] = Field(default_factory=list)
    model_count: int = 0


class ProjectDebugTarget(BaseModel):
    """不落盘调试所需的受控入口和内存源码覆盖。"""

    project_key: str
    project_type: str
    project_root: str
    entry_path: str
    script_path: str
    source_overrides: dict[str, str] = Field(default_factory=dict)


class ProjectPipelineDebugTarget(BaseModel):
    """Maa 项目源码描述文件解析出的 Pipeline 调试入口。"""

    project_key: str
    descriptor_path: str
    project_path: str
    entry: str
    override: dict[str, Any] = Field(default_factory=dict)
