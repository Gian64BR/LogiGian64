# Native Linux build. Never use the Windows vendor directory or DLLs.
a = Analysis(['main.py'], pathex=[], binaries=[],
    datas=[('assets','assets'),('licenses','licenses'),('LICENSE','.'),('THIRD_PARTY_NOTICES.md','.')],
    hiddenimports=['hid','evdev','pyudev'],
    excludes=['PySide6.QtWebEngineCore','PySide6.QtWebEngineWidgets','PySide6.QtQml','PySide6.QtQuick','tkinter'],
    noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='LogiGian64',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=True)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='LogiGian64')
