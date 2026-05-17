"""LLM 配置管理模块模型"""

from __future__ import annotations

import secrets
import string
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from mluascript.shared.config.registry import config

MaaStdoutLogLevel = Literal["off", "error", "warning", "info", "debug", "trace"]


def _random_config_secret() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(16))


@config.registry()
class WebServerConfig(BaseModel):
    """MluaScript Web 服务配置"""

    model_config = ConfigDict(extra="allow")

    host: str = Field(default="127.0.0.1", description="MluaScript Web 监听地址")
    port: int = Field(default=18080, ge=1, le=65535, description="MluaScript Web 监听端口")
    username: str = Field(default="admin", description="MluaScript Web 登录用户名")
    password: str = Field(default_factory=_random_config_secret, min_length=1, description="MluaScript Web 登录密码")
    session_secret: str = Field(default_factory=_random_config_secret, min_length=16, description="MluaScript Web 登录会话签名密钥")
    session_max_age_seconds: int = Field(default=604800, ge=60, description="MluaScript Web 登录有效期 秒")



@config.registry()
class GlobalConfig(BaseModel):
    """全局通用配置"""

    model_config = ConfigDict(extra="allow")

    log_level: str = Field(default="DEBUG", description="日志级别")
    log_dir: str = Field(default="./logs/app.log", description="宿主程序日志文件路径")
    stop_key: str = Field(default="F9", description="停止所有任务快捷键")
    start_key: str = Field(default="F10", description="启动上一个任务快捷键")
    scripts_path: list[str] = Field(default_factory=list, description="脚本路径列表")
    blockly_xml_dir: str = Field(default="blockly", description="Blockly XML 保存目录 默认运行路径下 blockly 文件夹")
    maa_library_dir: str = Field(default="", description="MAA 库目录路径")
    maa_resource_dir: str = Field(default="", description="MAA 资源目录路径")
    maa_model_dir: str = Field(default="./model", description="MAA 模型目录路径")
    maa_adb_dir: str = Field(default="", description="MAA ADB 目录路径")
    maa_log_dir: str = Field(default="./logs/maa.log", description="MAA 底层日志文件路径")
    maa_stdout_level: MaaStdoutLogLevel = Field(default="off", description="MAA 底层 stdout 日志级别")
    extra: dict[str, Any] = Field(default_factory=dict, description="其他扩展配置")
