"""Windows startup registration shared by the installer and settings menu."""
import subprocess
import sys
import winreg

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "LogiGian64"


def startup_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
            return bool(value)
    except FileNotFoundError:
        return False


def set_startup(enabled):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            command = [sys.executable]
            if not getattr(sys, "frozen", False):
                from pathlib import Path
                command.append(str(Path(__file__).resolve().parent.parent / "main.py"))
            command.append("--startup")
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, subprocess.list2cmdline(command))
        else:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                pass
