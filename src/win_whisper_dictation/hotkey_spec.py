from __future__ import annotations

import ctypes
import os
import random
import re
from dataclasses import dataclass
from typing import Iterable


MODIFIER_ORDER = ("ctrl", "alt", "shift", "win")
MOUSE_ORDER = ("mouse_x1", "mouse_x2", "mouse_middle", "mouse_left", "mouse_right")
MODIFIER_FAMILIES = {
    "ctrl": ("ctrl", "ctrl_l", "ctrl_r"),
    "alt": ("alt", "alt_l", "alt_r"),
    "shift": ("shift", "shift_l", "shift_r"),
    "win": ("win", "win_l", "win_r"),
}
SIDE_TO_GENERIC = {
    "ctrl_l": "ctrl",
    "ctrl_r": "ctrl",
    "alt_l": "alt",
    "alt_r": "alt",
    "shift_l": "shift",
    "shift_r": "shift",
    "win_l": "win",
    "win_r": "win",
}
GENERIC_MODIFIERS = set(MODIFIER_FAMILIES)
ANY_MODIFIER = set(GENERIC_MODIFIERS)
for values in MODIFIER_FAMILIES.values():
    ANY_MODIFIER.update(values)

DISPLAY_NAMES = {
    "ctrl": "Ctrl",
    "ctrl_l": "Left Ctrl",
    "ctrl_r": "Right Ctrl",
    "alt": "Alt",
    "alt_l": "Left Alt",
    "alt_r": "Right Alt",
    "shift": "Shift",
    "shift_l": "Left Shift",
    "shift_r": "Right Shift",
    "win": "Win",
    "win_l": "Left Win",
    "win_r": "Right Win",
    "space": "Space",
    "tab": "Tab",
    "delete": "Delete",
    "escape": "Esc",
    "enter": "Enter",
    "backspace": "Backspace",
    "caps_lock": "Caps Lock",
    "mouse_x1": "Mouse Back",
    "mouse_x2": "Mouse Forward",
    "mouse_middle": "Middle Mouse",
    "mouse_left": "Left Mouse",
    "mouse_right": "Right Mouse",
}

TOKEN_ALIASES = {
    "control": "ctrl",
    "ctl": "ctrl",
    "left ctrl": "ctrl_l",
    "left control": "ctrl_l",
    "ctrl left": "ctrl_l",
    "right ctrl": "ctrl_r",
    "right control": "ctrl_r",
    "ctrl right": "ctrl_r",
    "option": "alt",
    "left alt": "alt_l",
    "alt left": "alt_l",
    "right alt": "alt_r",
    "alt right": "alt_r",
    "left shift": "shift_l",
    "shift left": "shift_l",
    "right shift": "shift_r",
    "shift right": "shift_r",
    "rshift": "shift_r",
    "lshift": "shift_l",
    "windows": "win",
    "cmd": "win",
    "command": "win",
    "left win": "win_l",
    "win left": "win_l",
    "right win": "win_r",
    "win right": "win_r",
    "spacebar": "space",
    " ": "space",
    "esc": "escape",
    "del": "delete",
    "return": "enter",
    "bksp": "backspace",
    "x1": "mouse_x1",
    "x2": "mouse_x2",
    "mouse back": "mouse_x1",
    "mouse backward": "mouse_x1",
    "back mouse": "mouse_x1",
    "side mouse 1": "mouse_x1",
    "mouse side 1": "mouse_x1",
    "mouse forward": "mouse_x2",
    "forward mouse": "mouse_x2",
    "side mouse 2": "mouse_x2",
    "mouse side 2": "mouse_x2",
    "middle mouse": "mouse_middle",
    "mouse middle": "mouse_middle",
    "mouse wheel": "mouse_middle",
    "left mouse": "mouse_left",
    "mouse left": "mouse_left",
    "right mouse": "mouse_right",
    "mouse right": "mouse_right",
}

RUSSIAN_LAYOUT_TO_LATIN = {
    "\u0439": "q",
    "\u0446": "w",
    "\u0443": "e",
    "\u043a": "r",
    "\u0435": "t",
    "\u043d": "y",
    "\u0433": "u",
    "\u0448": "i",
    "\u0449": "o",
    "\u0437": "p",
    "\u0444": "a",
    "\u044b": "s",
    "\u0432": "d",
    "\u0430": "f",
    "\u043f": "g",
    "\u0440": "h",
    "\u043e": "j",
    "\u043b": "k",
    "\u0434": "l",
    "\u044f": "z",
    "\u0447": "x",
    "\u0441": "c",
    "\u043c": "v",
    "\u0438": "b",
    "\u0442": "n",
    "\u044c": "m",
}

VK_CODES = {
    "backspace": 0x08,
    "tab": 0x09,
    "enter": 0x0D,
    "shift": 0x10,
    "ctrl": 0x11,
    "alt": 0x12,
    "caps_lock": 0x14,
    "escape": 0x1B,
    "space": 0x20,
    "delete": 0x2E,
    "win": 0x5B,
    "win_l": 0x5B,
    "win_r": 0x5C,
    "shift_l": 0xA0,
    "shift_r": 0xA1,
    "ctrl_l": 0xA2,
    "ctrl_r": 0xA3,
    "alt_l": 0xA4,
    "alt_r": 0xA5,
}
for index in range(1, 25):
    VK_CODES[f"f{index}"] = 0x6F + index


@dataclass(frozen=True)
class HotkeySpec:
    tokens: tuple[str, ...]

    @property
    def canonical(self) -> str:
        return "+".join(self.tokens)

    @property
    def display(self) -> str:
        return " + ".join(display_token(token) for token in self.tokens)


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    message: str = ""


def normalize_token(raw: str) -> str:
    value = raw.strip().lower()
    value = value.replace("-", " ").replace("_", " ")
    value = re.sub(r"\s+", " ", value)
    value = TOKEN_ALIASES.get(value, value)
    value = value.replace(" ", "_")
    value = RUSSIAN_LAYOUT_TO_LATIN.get(value, value)

    if len(value) == 1 and value.isascii() and value.isalpha():
        return value
    if len(value) == 1 and value.isdigit():
        return value
    if re.fullmatch(r"f([1-9]|1[0-9]|2[0-4])", value):
        return value
    if value in MOUSE_ORDER:
        return value
    if value in VK_CODES or value in ANY_MODIFIER:
        return value
    raise ValueError(f"Неподдерживаемая клавиша: {raw}")


def display_token(token: str) -> str:
    if token in DISPLAY_NAMES:
        return DISPLAY_NAMES[token]
    if re.fullmatch(r"f([1-9]|1[0-9]|2[0-4])", token):
        return token.upper()
    if len(token) == 1:
        return token.upper()
    return token.replace("_", " ").title()


def parse_hotkey(raw: str | Iterable[str]) -> HotkeySpec:
    if isinstance(raw, str):
        parts = [part for part in re.split(r"\s*\+\s*", raw.strip()) if part]
    else:
        parts = list(raw)
    if not parts:
        raise ValueError("Горячая клавиша не задана")

    tokens = [normalize_token(part) for part in parts]
    return make_hotkey_spec(tokens)


def make_hotkey_spec(tokens: Iterable[str]) -> HotkeySpec:
    clean: list[str] = []
    for token in tokens:
        normalized = normalize_token(token)
        if normalized not in clean:
            clean.append(normalized)

    has_non_modifier = any(token not in ANY_MODIFIER for token in clean)
    if len(clean) > 1 and has_non_modifier:
        clean = [SIDE_TO_GENERIC.get(token, token) for token in clean]
        clean = list(dict.fromkeys(clean))

    ordered = sorted(clean, key=_sort_key)
    return HotkeySpec(tuple(ordered))


def validate_hotkey_format(spec: HotkeySpec | str) -> ValidationResult:
    try:
        hotkey = parse_hotkey(spec) if isinstance(spec, str) else spec
    except ValueError as exc:
        return ValidationResult(False, str(exc))

    tokens = set(hotkey.tokens)
    if not tokens:
        return ValidationResult(False, "Горячая клавиша не задана")
    if len(tokens) == 1 and next(iter(tokens)) in {
        "ctrl",
        "ctrl_l",
        "ctrl_r",
        "alt",
        "alt_l",
        "alt_r",
        "win",
        "win_l",
        "win_r",
    }:
        return ValidationResult(False, "Нельзя использовать только Ctrl, Alt или Win")
    if len(tokens) > 1 and all(token in ANY_MODIFIER for token in tokens) and not _allowed_modifier_only(tokens):
        return ValidationResult(False, "Сочетание только из этих модификаторов не поддерживается")
    if tokens & {"mouse_left", "mouse_right"} and len(tokens) == 1:
        return ValidationResult(False, "Левую и правую кнопку мыши нельзя использовать отдельно")
    if "alt" in _generic_set(tokens) and "tab" in tokens:
        return ValidationResult(False, "Alt+Tab зарезервирован Windows")
    if {"ctrl", "alt"}.issubset(_generic_set(tokens)) and "delete" in tokens:
        return ValidationResult(False, "Ctrl+Alt+Delete зарезервирован Windows")
    if "win" in _generic_set(tokens) and "l" in tokens:
        return ValidationResult(False, "Win+L зарезервирован Windows")
    return ValidationResult(True)


def validate_hotkey_system(spec: HotkeySpec | str) -> ValidationResult:
    hotkey = parse_hotkey(spec) if isinstance(spec, str) else spec
    result = validate_hotkey_format(hotkey)
    if not result.ok:
        return result
    if os.name != "nt":
        return ValidationResult(True)

    registration = _try_register_hotkey(hotkey)
    if registration.ok:
        return registration

    # Windows RegisterHotKey does not reserve mouse buttons and modifier-only
    # combos reliably, but the global listeners can still use them for hold-to-talk.
    tokens = set(hotkey.tokens)
    if tokens & set(MOUSE_ORDER) or tokens.issubset(ANY_MODIFIER):
        return ValidationResult(True)
    return registration


def token_matches(required_token: str, pressed_tokens: set[str]) -> bool:
    if required_token in pressed_tokens:
        return True
    generic = SIDE_TO_GENERIC.get(required_token)
    if generic and generic in pressed_tokens:
        return True
    family = MODIFIER_FAMILIES.get(required_token)
    if not family and generic:
        family = MODIFIER_FAMILIES.get(generic)
    return bool(family and any(token in pressed_tokens for token in family))


def released_token_affects_hotkey(released_token: str, required_tokens: Iterable[str]) -> bool:
    for required in required_tokens:
        if required == released_token:
            return True
        if SIDE_TO_GENERIC.get(required) == released_token:
            return True
        if SIDE_TO_GENERIC.get(released_token) == required:
            return True
        family = MODIFIER_FAMILIES.get(required)
        if not family:
            generic = SIDE_TO_GENERIC.get(required)
            if generic:
                family = MODIFIER_FAMILIES.get(generic)
        if family and released_token in family:
            return True
    return False


def _try_register_hotkey(hotkey: HotkeySpec) -> ValidationResult:
    modifiers, vk = _windows_hotkey_parts(hotkey)
    if vk is None:
        return ValidationResult(False, "Эта клавиша не поддерживается регистрацией горячих клавиш Windows")

    user32 = ctypes.windll.user32
    hotkey_id = random.randint(0x4000, 0x7FFF)
    ok = bool(user32.RegisterHotKey(None, hotkey_id, modifiers, vk))
    if not ok:
        return ValidationResult(False, "Windows не смог зарезервировать эту горячую клавишу")
    user32.UnregisterHotKey(None, hotkey_id)
    return ValidationResult(True)


def _windows_hotkey_parts(hotkey: HotkeySpec) -> tuple[int, int | None]:
    generic = _generic_set(hotkey.tokens)
    modifiers = 0
    if "alt" in generic:
        modifiers |= 0x0001
    if "ctrl" in generic:
        modifiers |= 0x0002
    if "shift" in generic and len(hotkey.tokens) > 1:
        modifiers |= 0x0004
    if "win" in generic:
        modifiers |= 0x0008

    main_tokens = [token for token in hotkey.tokens if token not in ANY_MODIFIER and token not in MOUSE_ORDER]
    if main_tokens:
        vk = _vk_code(main_tokens[-1])
    elif len(hotkey.tokens) == 1:
        vk = _vk_code(hotkey.tokens[0])
    else:
        vk = None
    return modifiers, vk


def _vk_code(token: str) -> int | None:
    if token in VK_CODES:
        return VK_CODES[token]
    if len(token) == 1 and token.isascii() and token.isalpha():
        return ord(token.upper())
    if len(token) == 1 and token.isdigit():
        return ord(token)
    return None


def _generic_set(tokens: Iterable[str]) -> set[str]:
    return {SIDE_TO_GENERIC.get(token, token) for token in tokens}


def _sort_key(token: str) -> tuple[int, str]:
    generic = SIDE_TO_GENERIC.get(token, token)
    if generic in MODIFIER_ORDER:
        return (MODIFIER_ORDER.index(generic), token)
    if token in MOUSE_ORDER:
        return (len(MODIFIER_ORDER) + MOUSE_ORDER.index(token), token)
    return (len(MODIFIER_ORDER) + len(MOUSE_ORDER), token)


def _allowed_modifier_only(tokens: set[str]) -> bool:
    generic = _generic_set(tokens)
    return len(generic) >= 2 and generic != {"ctrl", "alt"}
