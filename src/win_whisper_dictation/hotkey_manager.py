from __future__ import annotations

import threading
from collections.abc import Callable

from pynput import keyboard

from .hotkey_spec import (
    HotkeySpec,
    RUSSIAN_LAYOUT_TO_LATIN,
    make_hotkey_spec,
    parse_hotkey,
    released_token_affects_hotkey,
    token_matches,
    validate_hotkey_format,
)


CaptureUpdate = Callable[[str], None]
CaptureComplete = Callable[[str, str], None]
CaptureError = Callable[[str], None]

VK_TO_TOKEN = {
    **{0x30 + index: str(index) for index in range(10)},
    **{0x41 + index: chr(ord("a") + index) for index in range(26)},
}


class HotkeyManager:
    def __init__(self, hotkey: str, on_start: Callable[[], None], on_stop: Callable[[], None]):
        self._spec = parse_hotkey(hotkey)
        self._on_start = on_start
        self._on_stop = on_stop
        self._pressed: set[str] = set()
        self._active = False
        self._lock = threading.RLock()
        self._listener: keyboard.Listener | None = None

        self._capture_active = False
        self._capture_pressed: set[str] = set()
        self._capture_tokens: list[str] = []
        self._capture_update: CaptureUpdate | None = None
        self._capture_complete: CaptureComplete | None = None
        self._capture_error: CaptureError | None = None

    @property
    def hotkey(self) -> HotkeySpec:
        with self._lock:
            return self._spec

    def start(self) -> None:
        with self._lock:
            if self._listener:
                return
            self._listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
            self._listener.start()

    def stop(self) -> None:
        with self._lock:
            listener = self._listener
            self._listener = None
        if listener:
            listener.stop()

    def set_hotkey(self, hotkey: str) -> None:
        spec = parse_hotkey(hotkey)
        result = validate_hotkey_format(spec)
        if not result.ok:
            raise ValueError(result.message)
        with self._lock:
            self._spec = spec
            self._active = False
            self._pressed.clear()

    def begin_capture(
        self,
        on_update: CaptureUpdate,
        on_complete: CaptureComplete,
        on_error: CaptureError,
    ) -> None:
        with self._lock:
            self._capture_active = True
            self._capture_pressed.clear()
            self._capture_tokens.clear()
            self._capture_update = on_update
            self._capture_complete = on_complete
            self._capture_error = on_error

    def cancel_capture(self) -> None:
        with self._lock:
            self._capture_active = False
            self._capture_pressed.clear()
            self._capture_tokens.clear()
            self._capture_update = None
            self._capture_complete = None
            self._capture_error = None

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        token = key_to_token(key)
        if not token:
            return

        start = False
        with self._lock:
            if self._capture_active:
                self._capture_pressed.add(token)
                if token not in self._capture_tokens:
                    self._capture_tokens.append(token)
                update = self._capture_update
                display = make_hotkey_spec(self._capture_tokens).display
            else:
                update = None
                display = ""
                self._pressed.add(token)
                if not self._active and self._is_hotkey_pressed():
                    self._active = True
                    start = True

        if update:
            update(display)
        if start:
            self._on_start()

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        token = key_to_token(key)
        if not token:
            return

        stop = False
        complete: tuple[CaptureComplete, str, str] | None = None
        error: tuple[CaptureError, str] | None = None
        with self._lock:
            if self._capture_active:
                self._capture_pressed.discard(token)
                if not self._capture_pressed and self._capture_tokens:
                    try:
                        spec = make_hotkey_spec(self._capture_tokens)
                        result = validate_hotkey_format(spec)
                        if result.ok:
                            if self._capture_complete:
                                complete = (self._capture_complete, spec.canonical, spec.display)
                        elif self._capture_error:
                            error = (self._capture_error, result.message)
                    except ValueError as exc:
                        if self._capture_error:
                            error = (self._capture_error, str(exc))
                    self.cancel_capture()
            else:
                self._pressed.discard(token)
                if self._active and released_token_affects_hotkey(token, self._spec.tokens):
                    self._active = False
                    stop = True

        if complete:
            callback, canonical, display = complete
            callback(canonical, display)
        if error:
            callback, message = error
            callback(message)
        if stop:
            self._on_stop()

    def _is_hotkey_pressed(self) -> bool:
        return all(token_matches(token, self._pressed) for token in self._spec.tokens)


def key_to_token(key: keyboard.Key | keyboard.KeyCode) -> str | None:
    special_map = {
        keyboard.Key.shift: "shift",
        keyboard.Key.shift_l: "shift_l",
        keyboard.Key.shift_r: "shift_r",
        keyboard.Key.ctrl: "ctrl",
        keyboard.Key.ctrl_l: "ctrl_l",
        keyboard.Key.ctrl_r: "ctrl_r",
        keyboard.Key.alt: "alt",
        keyboard.Key.alt_l: "alt_l",
        keyboard.Key.alt_r: "alt_r",
        keyboard.Key.cmd: "win",
        keyboard.Key.cmd_l: "win_l",
        keyboard.Key.cmd_r: "win_r",
        keyboard.Key.space: "space",
        keyboard.Key.tab: "tab",
        keyboard.Key.delete: "delete",
        keyboard.Key.esc: "escape",
        keyboard.Key.enter: "enter",
        keyboard.Key.backspace: "backspace",
        keyboard.Key.caps_lock: "caps_lock",
    }
    for index in range(1, 25):
        enum_key = getattr(keyboard.Key, f"f{index}", None)
        if enum_key is not None:
            special_map[enum_key] = f"f{index}"

    if key in special_map:
        return special_map[key]
    if isinstance(key, keyboard.KeyCode):
        vk = getattr(key, "vk", None)
        if isinstance(vk, int) and vk in VK_TO_TOKEN:
            return VK_TO_TOKEN[vk]
        if key.char:
            char = key.char.lower()
            if char == " ":
                return "space"
            if char in RUSSIAN_LAYOUT_TO_LATIN:
                return RUSSIAN_LAYOUT_TO_LATIN[char]
            if len(char) == 1 and char.isascii() and (char.isalpha() or char.isdigit()):
                return char
    return None
