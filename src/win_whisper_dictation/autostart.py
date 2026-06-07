from __future__ import annotations

import os
import sys
from pathlib import Path


APP_RUN_NAME = "VoiceType"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def is_supported() -> bool:
    return os.name == "nt"


def current_launch_command() -> str:
    if getattr(sys, "frozen", False):
        return _quote(sys.executable)

    pythonw = Path(sys.executable).with_name("pythonw.exe")
    executable = pythonw if pythonw.exists() else Path(sys.executable)
    return f"{_quote(str(executable))} -m win_whisper_dictation"


def set_autostart(enabled: bool, command: str | None = None) -> None:
    if not is_supported():
        return
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, APP_RUN_NAME, 0, winreg.REG_SZ, command or current_launch_command())
        else:
            try:
                winreg.DeleteValue(key, APP_RUN_NAME)
            except FileNotFoundError:
                pass


def is_enabled() -> bool:
    if not is_supported():
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, APP_RUN_NAME)
            return True
    except FileNotFoundError:
        return False


def _quote(value: str) -> str:
    return f'"{value}"'
