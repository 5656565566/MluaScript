# -*- mode: python ; coding: utf-8 -*-
import os
import shutil
import sys
import subprocess
from pathlib import Path

from PyInstaller.building.utils import format_binaries_and_datas
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs


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
    webui_dist_path = webui_path / 'dist'
    
    if not webui_path.exists():
        return False
    
    print("Building frontend...")
    
    try:
        # 打包前移除旧产物 避免构建失败时把过期 Web 资源带入新可执行文件
        if webui_dist_path.exists():
            shutil.rmtree(webui_dist_path)

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
            
        if result.returncode != 0:
            return False

        index_file = webui_dist_path / 'index.html'
        if not index_file.is_file():
            _safe_print(f"Frontend build did not produce {index_file}")
            return False

        return True
        
    except Exception as e:
        _safe_print(f"Build error: {e}")
        return False

# 构建前端
if not build_frontend():
    raise SystemExit("Frontend build failed; packaging aborted to avoid stale Web assets")

# 继续打包配置...
import maa

maa_bin_path = os.path.join(os.path.dirname(maa.__file__), 'bin')
maa_agent_files = [
    *collect_data_files('MaaAgentBinary'),
    *collect_dynamic_libs('MaaAgentBinary', search_patterns=['*.so']),
]
webui_dist_path = os.path.abspath('src/mluascript_web/dist')
upx_dir = os.path.abspath('dev/upx-5.1.1-win64')
resolved_upx_dir = upx_dir if os.path.isdir(upx_dir) else None
resolved_icon = 'logo.ico' if sys.platform.startswith('win') and os.path.exists('logo.ico') else None

# Android 端触控程序是独立数据包 PyInstaller 不会随 maa Python 模块自动收集
required_agent_assets = {
    'MaaAgentBinary/maatouch/universal/maatouch',
    'MaaAgentBinary/minitouch/arm64-v8a/minitouch',
    'MaaAgentBinary/minitouch/armeabi/minitouch',
    'MaaAgentBinary/minitouch/armeabi-v7a/minitouch',
    'MaaAgentBinary/minitouch/x86/minitouch',
    'MaaAgentBinary/minitouch/x86_64/minitouch',
}
collected_agent_assets = {
    (Path(destination) / Path(source).name).as_posix()
    for source, destination in maa_agent_files
}
missing_agent_assets = sorted(required_agent_assets - collected_agent_assets)
if missing_agent_assets:
    raise SystemExit(f"MaaAgentBinary assets missing: {', '.join(missing_agent_assets)}")
if not any(asset.endswith('/minicap.so') for asset in collected_agent_assets):
    raise SystemExit("MaaAgentBinary minicap.so assets missing")

maa_agent_toc = [
    (destination, source, 'DATA')
    for destination, source in format_binaries_and_datas(maa_agent_files)
]

a = Analysis(
    ['src/build.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        (maa_bin_path, '.'),
        (maa_bin_path, 'maa/bin'),
        (webui_dist_path, 'mluascript_web/dist'),
        ('src/mluascript/runtime/inject_lua/*.lua', 'mluascript/runtime/inject_lua'),
    ],
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

# Analysis 会把 Android ELF 误判为宿主机二进制 在分类完成后按数据文件追加 保留完整 Agent 包
a.datas.extend(maa_agent_toc)

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
