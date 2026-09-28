# -*- mode: python ; coding: utf-8 -*-
import os


ENGEL_RUNTIME_TMPDIR = os.path.abspath(os.path.join(os.getcwd(), 'runtime', 'pyinstaller_tmp'))
os.makedirs(ENGEL_RUNTIME_TMPDIR, exist_ok=True)


a = Analysis(
    ['engel_desktop_v2.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['pyinstaller_runtime_hooks\\engel_temp_runtime_hook.py'],
    excludes=["PyQt6", "PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtWidgets"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='EngelAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=ENGEL_RUNTIME_TMPDIR,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/branding/final/engel_icon_final.ico',
)
