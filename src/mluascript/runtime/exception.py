from lupa.lua54 import LuaError

class LuaExitException(LuaError):
    """Lua 强制退出"""
    pass