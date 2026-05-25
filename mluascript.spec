# -*- mode: python ; coding: utf-8 -*-
import os
import sys
import subprocess
import importlib.util
from pathlib import Path


def _safe_print(text):
    if text is None:
        return
    if not isinstance(text, str):
        text = str(text)
    try:
        print(text)
    except UnicodeEncodeError:
        stream = getattr(sys.stdout, "buffer", None)
        if stream is not None:
            stream.write(text.encode("utf-8", errors="replace"))
            if not text.endswith("\n"):
                stream.write(b"\n")
        else:
            print(text.encode("utf-8", errors="replace").decode("utf-8", errors="replace"))

def build_frontend():
    """构建前端项目"""
    webui_path = Path('src/mluascript_web')
    
    if not webui_path.exists():
        return False
    
    print("Building frontend...")
    
    try:
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'
        
        env['NO_COLOR'] = '1'
        env['FORCE_COLOR'] = '0'
        npm_command = 'npm.cmd' if sys.platform.startswith('win') else 'npm'
        
        result = subprocess.run(
            [npm_command, 'run', 'build'],
            cwd=str(webui_path),
            capture_output=True,
            text=True,
            env=env,
            encoding='utf-8',
            errors='replace',
            shell=False
        )
        
        _safe_print(result.stdout)
        if result.stderr:
            _safe_print(result.stderr)
            
        return result.returncode == 0
        
    except Exception as e:
        _safe_print(f"Build error: {e}")
        return False

# 构建前端
if not build_frontend():
    print("Frontend build failed")
    # 不退出，继续使用已有文件

# 继续打包配置...
import maa

maa_bin_path = os.path.join(os.path.dirname(maa.__file__), 'bin')
maa_agent_spec = importlib.util.find_spec('MaaAgentBinary')
maa_agent_binary_path = None
if maa_agent_spec is not None and maa_agent_spec.submodule_search_locations:
    maa_agent_binary_path = str(Path(next(iter(maa_agent_spec.submodule_search_locations))).resolve())
webui_dist_path = os.path.abspath('src/mluascript_web/dist')
upx_dir = os.path.abspath('dev/upx-5.1.1-win64')
resolved_upx_dir = upx_dir if os.path.isdir(upx_dir) else None
resolved_icon = 'logo.ico' if sys.platform.startswith('win') and os.path.exists('logo.ico') else None

datas = [
    (maa_bin_path, '.'),
    (maa_bin_path, 'maa/bin'),
    (webui_dist_path, 'mluascript_web/dist'),
    ('src/mluascript/runtime/inject_lua/*.lua', 'mluascript/runtime/inject_lua'),
]
if maa_agent_binary_path and os.path.isdir(maa_agent_binary_path):
    datas.append((maa_agent_binary_path, 'MaaAgentBinary'))

a = Analysis(
    ['src/build.py'],
    pathex=['src'],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'mluascript.frontends',
        'mluascript.frontends.tui',
        'mluascript.control.facade',
        'mluascript.maa.lifecycle.runtime',
        'textual.widgets._tab',
        'textual.widgets._tabs',
        'textual.widgets._tab_pane',
        'strenum',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='mluascript',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=resolved_upx_dir is not None,
    upx_dir=resolved_upx_dir,
    upx_exclude=['*.dll'],
    runtime_tmpdir=None,
    console=True,
    icon=resolved_icon,
    compress=True,
    optimize=2,
)
