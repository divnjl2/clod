# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Claude Agent Manager GUI
Cross-platform build configuration
"""

import sys
import os
from pathlib import Path

block_cipher = None

# Determine platform-specific settings
is_windows = sys.platform == 'win32'
is_macos = sys.platform == 'darwin'
is_linux = sys.platform.startswith('linux')

# Project paths
PROJECT_ROOT = Path(SPECPATH)
SRC_DIR = PROJECT_ROOT / 'src'
ASSETS_DIR = PROJECT_ROOT / 'assets'

# Icon paths
if is_windows:
    ICON_FILE = str(ASSETS_DIR / 'icon.ico')
elif is_macos:
    ICON_FILE = str(ASSETS_DIR / 'icon.icns') if (ASSETS_DIR / 'icon.icns').exists() else str(ASSETS_DIR / 'icon.png')
else:
    ICON_FILE = str(ASSETS_DIR / 'icon.png')

# Data files to include
datas = [
    (str(ASSETS_DIR / 'icon.png'), 'assets'),
    (str(SRC_DIR / 'claude_agent_manager' / 'viewer.html'), 'claude_agent_manager'),
    (str(SRC_DIR / 'claude_agent_manager' / 'subagent_mcp.py'), 'claude_agent_manager'),
]
if is_windows and (ASSETS_DIR / 'icon.ico').exists():
    datas.append((str(ASSETS_DIR / 'icon.ico'), 'assets'))

# Hidden imports for the application
hiddenimports = [
    'tkinter',
    'tkinter.ttk',
    'claude_agent_manager',
    'claude_agent_manager.simple_dashboard',
    'claude_agent_manager.config',
    'claude_agent_manager.processes',
    'claude_agent_manager.agent_config',
    'claude_agent_manager.manager',
    'claude_agent_manager.registry',
    'claude_agent_manager.settings',
    'claude_agent_manager.tile',
    'claude_agent_manager.hotkeys',
    'claude_agent_manager.custom_hotkeys',
    'claude_agent_manager.windows',
    'claude_agent_manager.worker',
    'claude_agent_manager.terminal',
    'claude_agent_manager.terminal.embedded_console',
    'claude_agent_manager.terminal.pty_backend',
    'claude_agent_manager.terminal.ansi_parser',
    'claude_agent_manager.terminal.widget',
    'claude_agent_manager.updater',
    'claude_agent_manager.sharing',
    'claude_agent_manager.sharing_cli',
    'claude_agent_manager.crew',
    'claude_agent_manager.subagents',
    'claude_agent_manager.subagent_mcp',
    'claude_agent_manager.memory_tools',
    'claude_agent_manager.memory_diagnostics',
    'claude_agent_manager.monitoring',
    'claude_agent_manager.overlay',
    'claude_agent_manager.cli',
    'pydantic',
    'psutil',
    'typer',
    'rich',
    'click',
]

# Platform-specific hidden imports
if is_windows:
    hiddenimports.extend([
        'pywinpty',
        'pyte',
        'ctypes',
        'ctypes.wintypes',
    ])

a = Analysis(
    [str(SRC_DIR / 'claude_agent_manager' / 'simple_dashboard.py')],
    pathex=[str(SRC_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',  # Not needed at runtime, only for icon conversion
        'pytest',
        'unittest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Claude Agent Manager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI app, no console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_FILE if os.path.exists(ICON_FILE) else None,
)

# macOS app bundle
if is_macos:
    app = BUNDLE(
        exe,
        name='Claude Agent Manager.app',
        icon=ICON_FILE if os.path.exists(ICON_FILE) else None,
        bundle_identifier='com.claude.agentmanager',
        info_plist={
            'CFBundleName': 'Claude Agent Manager',
            'CFBundleDisplayName': 'Claude Agent Manager',
            'CFBundleVersion': '0.1.0',
            'CFBundleShortVersionString': '0.1.0',
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '10.15',
        },
    )
