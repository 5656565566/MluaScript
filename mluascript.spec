# -*- mode: python ; coding: utf-8 -*-
import os
import sys
import subprocess
from pathlib import Path

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
        
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
            
        return result.returncode == 0
        
    except Exception as e:
        print(f"Build error: {e}")
        return False

# 构建前端
if not build_frontend():
    print("Frontend build failed")
    # 不退出，继续使用已有文件

# 继续打包配置...
import maa

maa_bin_path = os.path.join(os.path.dirname(maa.__file__), 'bin')
webui_dist_path = os.path.abspath('src/mluascript_web/dist')
upx_dir = os.path.abspath('dev/upx-5.1.1-win64')
resolved_upx_dir = upx_dir if os.path.isdir(upx_dir) else None
resolved_icon = 'logo.ico' if sys.platform.startswith('win') and os.path.exists('logo.ico') else None

a = Analysis(
    ['src/build.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        (maa_bin_path, 'maa/bin'),
        (webui_dist_path, 'mluascript_web/dist'),
        ('src/mluascript/runtime/inject_lua/*.lua', 'mluascript/runtime/inject_lua'),
    ],
    hiddenimports=[
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
