from pathlib import Path

from lupa.lua54 import LuaRuntime

CORE_MODULES = (
    "utils",
    "json",
    "results",
    "io_override",
    "log",
)

_STDLIB_DIR = Path(__file__).parent
_CACHE: dict[str, str] = {}


def load_lua_script(name: str) -> str:
    """加载单个 Lua 注入脚本"""
    if name not in _CACHE:
        script_path = _STDLIB_DIR / f"{name}.lua"
        if script_path.exists():
            _CACHE[name] = script_path.read_text(encoding="utf-8")
        else:
            raise FileNotFoundError(f"Lua file not found: {script_path}")
    return _CACHE[name]


def load_lua_scripts(*names: str) -> str:
    """按顺序加载并合并多个 Lua 注入脚本"""
    scripts = [load_lua_script(name) for name in names]
    return "\n\n".join(scripts)


def build_lua_runtime_inject(lupa: LuaRuntime) -> LuaRuntime:
    """向 LuaRuntime 注入默认运行环境"""
    lupa.execute(load_lua_scripts(*CORE_MODULES))
    return lupa
