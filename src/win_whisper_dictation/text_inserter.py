from __future__ import annotations

import ctypes
import time
from dataclasses import dataclass

import pyperclip
from pynput.keyboard import Controller, Key

from .config import AppConfig


SW_RESTORE = 9
VK_CONTROL = 0x11
VK_V = 0x56
KEYEVENTF_KEYUP = 0x0002


@dataclass(frozen=True)
class WindowInfo:
    hwnd: int
    title: str = ""


class TextInserter:
    def __init__(self, config: AppConfig):
        self._config = config
        self._keyboard = Controller()

    def update_config(self, config: AppConfig) -> None:
        self._config = config

    def insert(self, text: str, target_hwnd: int | None = None) -> None:
        if not text:
            return
        mode = self._config.paste_mode
        if mode == "typewrite":
            self._typewrite(text, target_hwnd)
            return
        try:
            self._clipboard_paste(text, target_hwnd)
        except Exception:
            if mode == "clipboard_then_typewrite":
                self._typewrite(text, target_hwnd)
                return
            raise

    def _clipboard_paste(self, text: str, target_hwnd: int | None) -> None:
        previous_text: str | None
        try:
            previous_text = pyperclip.paste()
        except pyperclip.PyperclipException:
            previous_text = None

        pyperclip.copy(text)
        time.sleep(0.12)
        focus_window(target_hwnd)
        time.sleep(0.12)
        _send_ctrl_v()
        time.sleep(max(0.1, self._config.clipboard_restore_delay_seconds))

        if self._config.restore_clipboard and previous_text is not None:
            pyperclip.copy(previous_text)

    def _typewrite(self, text: str, target_hwnd: int | None) -> None:
        focus_window(target_hwnd)
        time.sleep(0.12)
        self._keyboard.type(text)


def get_foreground_window() -> WindowInfo:
    if not hasattr(ctypes, "windll"):
        return WindowInfo(0, "")
    user32 = ctypes.windll.user32
    hwnd = int(user32.GetForegroundWindow())
    return WindowInfo(hwnd=hwnd, title=get_window_title(hwnd))


def get_window_title(hwnd: int) -> str:
    if not hwnd or not hasattr(ctypes, "windll"):
        return ""
    user32 = ctypes.windll.user32
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def focus_window(hwnd: int | None) -> None:
    if not hwnd or not hasattr(ctypes, "windll"):
        return
    user32 = ctypes.windll.user32
    if not user32.IsWindow(hwnd):
        return
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)


def _send_ctrl_v() -> None:
    if hasattr(ctypes, "windll"):
        user32 = ctypes.windll.user32
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(VK_V, 0, 0, 0)
        user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
        return

    keyboard = Controller()
    keyboard.press(Key.ctrl)
    keyboard.press("v")
    keyboard.release("v")
    keyboard.release(Key.ctrl)
