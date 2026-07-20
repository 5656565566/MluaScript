from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


TemplateScalar = str | int | float | bool | None
TemplateValue = TemplateScalar | list[Any] | dict[str, Any]
TemplateType = Literal["str", "int", "num", "bool", "enum", "json"]
TemplateInputStyle = Literal["path"]


class TemplateCondition(BaseModel):
    """字段显示/生效条件"""

    k: str = Field(default="", description="依赖字段 key")
    eq: TemplateValue = Field(default=None, description="等于指定值时生效")
    ne: TemplateValue = Field(default=None, description="不等于指定值时生效")
    gt: int | float | None = Field(default=None, description="大于指定数值时生效")
    gte: int | float | None = Field(default=None, description="大于等于指定数值时生效")
    lt: int | float | None = Field(default=None, description="小于指定数值时生效")
    lte: int | float | None = Field(default=None, description="小于等于指定数值时生效")
    in_: list[TemplateValue] = Field(default_factory=list, alias="in", description="位于集合内时生效")

    model_config = {
        "populate_by_name": True,
        "extra": "ignore",
    }


class TemplateOptionDef(BaseModel):
    """枚举选项定义"""

    v: TemplateValue = Field(default=None, description="选项值")
    t: str = Field(default="", description="显示标题")
    d: str = Field(default="", description="说明")
    model_config = {
        "extra": "ignore",
    }


class TemplateVarDef(BaseModel):
    """模板字段定义"""

    k: str = Field(default="", description="字段 key 在 vars 字典上下文中可省略")
    t: str = Field(default="", description="标题")
    d: str = Field(default="", description="说明")
    tp: TemplateType = Field(default="str", description="字段类型")
    ui: TemplateInputStyle | None = Field(default=None, description="输入控件样式；path 仅用于 str 字段")
    req: bool = Field(default=False, description="是否必填")
    def_: TemplateValue = Field(default=None, alias="def", description="默认值")
    min: float | None = Field(default=None, description="最小值")
    max: float | None = Field(default=None, description="最大值")
    pat: str = Field(default="", description="正则约束")
    note: str = Field(default="", description="注解/帮助")
    as_: str = Field(default="", alias="as", description="注入别名")
    one_of: list[TemplateOptionDef] = Field(default_factory=list, alias="oneOf", description="枚举选项")
    ext: dict[str, Any] = Field(default_factory=dict, description="扩展字段")

    model_config = {
        "populate_by_name": True,
        "extra": "ignore",
    }

    @field_validator("k", "t", "d", "pat", "note", mode="before")
    @classmethod
    def _normalize_text(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @field_validator("as_", mode="before")
    @classmethod
    def _normalize_alias(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @model_validator(mode="after")
    def _validate_input_style(self) -> "TemplateVarDef":
        if self.ui is not None and self.tp != "str":
            raise ValueError("ui 仅适用于 str 字段")
        return self


class TemplateTaskArgDef(BaseModel):
    """任务对模板参数的引用及任务内关系"""

    k: str = Field(default="", description="引用字段 key")
    if_: TemplateCondition | None = Field(default=None, alias="if", description="任务内生效条件")

    model_config = {
        "populate_by_name": True,
        "extra": "ignore",
    }


TemplateTaskArgRef = str | TemplateTaskArgDef


class TemplateTaskDef(BaseModel):
    """任务原型定义"""

    k: str = Field(default="", description="任务 key")
    t: str = Field(default="", description="标题")
    d: str = Field(default="", description="说明")
    ut: str = Field(default="", description="用户标题")
    ud: str = Field(default="", description="用户说明")
    fn: str = Field(default="", description="Lua 函数引用")
    args: list[TemplateTaskArgRef] = Field(default_factory=list, description="字段 key 或带任务内关系的字段引用")
    defaults: dict[str, Any] = Field(default_factory=dict, description="任务级默认参数")
    ext: dict[str, Any] = Field(default_factory=dict, description="扩展字段")

    model_config = {
        "extra": "ignore",
    }

    @model_validator(mode="after")
    def _validate_arg_relations(self) -> "TemplateTaskDef":
        keys = [arg if isinstance(arg, str) else arg.k for arg in self.args]
        if any(not key for key in keys):
            raise ValueError(f"任务 {self.k or '未命名任务'} 存在空参数引用")
        if len(keys) != len(set(keys)):
            raise ValueError(f"任务 {self.k or '未命名任务'} 存在重复参数引用")
        key_set = set(keys)
        for arg in self.args:
            if isinstance(arg, str) or arg.if_ is None:
                continue
            if arg.if_.k == arg.k:
                raise ValueError(f"任务参数 {arg.k} 不能依赖自身")
            if arg.if_.k not in key_set:
                raise ValueError(f"任务参数 {arg.k} 依赖了任务未引用的参数: {arg.if_.k}")
        return self


class TemplateStepDef(BaseModel):
    """工作流步骤定义"""

    k: str = Field(default="", description="步骤 key")
    t: str = Field(default="", description="标题")
    d: str = Field(default="", description="说明")
    ut: str = Field(default="", description="用户标题")
    ud: str = Field(default="", description="用户说明")
    task: str = Field(default="", description="引用 task key")
    args: dict[str, Any] = Field(default_factory=dict, description="步骤默认覆盖参数")
    enabled: bool = Field(default=True, description="默认启用")
    onSuccess: str = Field(default="continue", description="成功策略")
    successGoto: str = Field(default="", description="成功时跳转的步骤 key")
    onFail: str = Field(default="stop", description="失败策略")
    goto: str = Field(default="", description="失败时跳转的步骤 key")
    allowDisable: bool = Field(default=True, description="允许用户禁用")
    allowReorder: bool = Field(default=True, description="允许用户重排")
    ext: dict[str, Any] = Field(default_factory=dict, description="扩展字段")

    model_config = {
        "extra": "ignore",
    }


class TemplateFlowDef(BaseModel):
    """工作流定义"""

    k: str = Field(default="", description="工作流 key")
    t: str = Field(default="", description="标题")
    d: str = Field(default="", description="说明")
    ut: str = Field(default="", description="用户标题")
    ud: str = Field(default="", description="用户说明")
    g: list[str] = Field(default_factory=list, description="全局字段引用")
    steps: list[TemplateStepDef] = Field(default_factory=list, description="步骤列表")
    ext: dict[str, Any] = Field(default_factory=dict, description="扩展字段")

    model_config = {
        "extra": "ignore",
    }


class TemplateEntryDef(BaseModel):
    """模板默认入口"""

    flow: str = Field(default="", description="默认工作流 key")
    task: str = Field(default="", description="默认任务 key")

    model_config = {
        "extra": "ignore",
    }


class TemplateMeta(BaseModel):
    """标准化后的模板元数据"""

    v: int = Field(default=1, description="模板版本")
    id: str = Field(default="", description="模板 id")
    t: str = Field(default="", description="标题")
    d: str = Field(default="", description="说明")
    ut: str = Field(default="", description="用户标题")
    ud: str = Field(default="", description="用户说明")
    mode: str = Field(default="wf", description="模板模式：wf/task")
    vars: dict[str, TemplateVarDef] = Field(default_factory=dict, description="拍平后的字段表")
    tasks: list[TemplateTaskDef] = Field(default_factory=list, description="任务原型列表")
    flows: list[TemplateFlowDef] = Field(default_factory=list, description="工作流列表")
    entry: TemplateEntryDef = Field(default_factory=TemplateEntryDef)
    ext: dict[str, Any] = Field(default_factory=dict, description="扩展字段")

    model_config = {
        "extra": "ignore",
    }

    @model_validator(mode="after")
    def _fill_entry_defaults(self) -> "TemplateMeta":
        if not self.entry.flow and self.flows:
            self.entry.flow = self.flows[0].k
        if not self.entry.task and self.tasks:
            self.entry.task = self.tasks[0].k
        return self


class SavedTaskConfig(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)


class SavedFlowConfig(BaseModel):
    stepArgs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    stepEnabled: dict[str, bool] = Field(default_factory=dict)
    stepOrder: list[str] = Field(default_factory=list)
    globals: dict[str, Any] = Field(default_factory=dict)


class TemplateSavedConfig(BaseModel):
    scriptPath: str = ""
    updatedAt: str = ""
    selectedTaskKey: str = ""
    selectedFlowKey: str = ""
    tasks: dict[str, SavedTaskConfig] = Field(default_factory=dict)
    flows: dict[str, SavedFlowConfig] = Field(default_factory=dict)
