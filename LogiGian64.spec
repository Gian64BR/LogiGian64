# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import PySide6


a = Analysis(
    ['main.py'],
    pathex=['vendor'],
    binaries=[],
    datas=[('assets', 'assets'), ('LICENSE', '.'), ('THIRD_PARTY_NOTICES.md', '.'), ('licenses', 'licenses')],
    hiddenimports=['hid'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtQml', 'PySide6.QtQuick', 'tkinter'],
    noarchive=False,
    optimize=0,
)
# The build host has third-party UCRT/API-set DLLs on PATH. On Windows 10+
# these are OS components; bundling them shadows the OS and breaks Qt loading.
qt_dir = Path(PySide6.__file__).parent
a.binaries = [entry for entry in a.binaries
              if not Path(entry[0]).name.lower().startswith('api-ms-win-')
              and Path(entry[0]).name.lower() not in ('ucrtbase.dll', 'icuuc.dll', 'icuin.dll')
              and not Path(entry[0]).name.lower().startswith('icudt')
              and not ('\\' not in entry[0] and '/' not in entry[0]
                       and Path(entry[0]).name.lower() in ('vcruntime140.dll', 'vcruntime140_1.dll'))]
for runtime in ('vcruntime140.dll', 'vcruntime140_1.dll', 'msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll'):
    source = qt_dir / runtime
    if source.exists():
        a.binaries.append((runtime, str(source), 'BINARY'))
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='LogiGian64',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='version.txt',
    icon=['assets/logigian64.ico'],
)
