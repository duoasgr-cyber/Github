# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

datas = [
    ('config', 'config'),
    ('tp', 'tp'),
    ('lib/scrcpy-server.jar', 'lib'),
    ('ui/resources', 'ui/resources'),
]

hiddenimports = [
    'easyocr',
    'cv2',
    'numpy',
    'PyQt5',
]

excludes = [
    'tkinter',
    'pystray',
]

icon_path = 'ui/resources/icons/app.svg'
if not os.path.exists(icon_path):
    icon_path = None
elif not icon_path.endswith('.ico'):
    ico_path = icon_path.rsplit('.', 1)[0] + '.ico'
    icon_path = ico_path if os.path.exists(ico_path) else None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='三角洲自动抢购工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=icon_path,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='三角洲自动抢购工具',
)
