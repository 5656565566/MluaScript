"""可打包项目的虚拟 Lua 模块路径规则。"""

from __future__ import annotations

from pathlib import PurePosixPath

from .package_builder import normalize_package_path


BLOCKLY_SOURCE_ROOT = "blockly"
SCRIPT_ROOT = "scripts"


def blockly_source_to_script_path(source_path: str) -> str:
    """把 ``blockly/**/*.xml`` 映射为包内 ``scripts/**/*.lua``。"""

    normalized = normalize_package_path(source_path)
    path = PurePosixPath(normalized)
    if not path.parts or path.parts[0] != BLOCKLY_SOURCE_ROOT or path.suffix.casefold() != ".xml":
        raise ValueError("Blockly 源文件必须是 blockly/ 目录内的 .xml 文件")
    relative = PurePosixPath(*path.parts[1:])
    if not relative.parts:
        raise ValueError("Blockly 源文件路径不能为空")
    return (PurePosixPath(SCRIPT_ROOT) / relative.with_suffix(".lua")).as_posix()


def script_path_to_module_key(script_path: str) -> str:
    """把 ``scripts/**/*.lua`` 转换为稳定的项目模块键。"""

    normalized = normalize_package_path(script_path)
    path = PurePosixPath(normalized)
    if not path.parts or path.parts[0] != SCRIPT_ROOT or path.suffix.casefold() != ".lua":
        raise ValueError("Lua 模块必须是 scripts/ 目录内的 .lua 文件")
    relative = PurePosixPath(*path.parts[1:])
    if not relative.parts:
        raise ValueError("Lua 模块路径不能为空")
    if relative.name.casefold() == "init.lua" and len(relative.parts) > 1:
        return relative.parent.as_posix()
    return relative.with_suffix("").as_posix()


def blockly_source_to_module_key(source_path: str) -> str:
    """返回 Blockly 源文件对应的项目模块键。"""

    return script_path_to_module_key(blockly_source_to_script_path(source_path))
