from __future__ import annotations


class MaaError(Exception):
    """Maa 核心通用异常"""


class MaaBootstrapError(MaaError):
    """Maa 初始化失败"""


class MaaConnectionError(MaaError):
    """Maa 连接失败"""


class MaaResourceError(MaaError):
    """Maa 资源操作失败"""
