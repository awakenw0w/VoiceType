import unittest

from pynput import keyboard, mouse

from win_whisper_dictation.config import AppConfig
from win_whisper_dictation.hotkey_manager import key_to_token, mouse_button_to_token
from win_whisper_dictation.hotkey_spec import parse_hotkey, token_matches, validate_hotkey_format


class HotkeySpecTests(unittest.TestCase):
    def test_examples_are_normalized(self):
        cases = {
            "Right Shift": ("shift_r", "Right Shift"),
            "Ctrl + Alt + Space": ("ctrl+alt+space", "Ctrl + Alt + Space"),
            "F8": ("f8", "F8"),
            "Ctrl+Shift+D": ("ctrl+shift+d", "Ctrl + Shift + D"),
            "Shift+Win": ("shift+win", "Shift + Win"),
            "Mouse Back": ("mouse_x1", "Mouse Back"),
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                spec = parse_hotkey(raw)
                self.assertEqual(spec.canonical, expected[0])
                self.assertEqual(spec.display, expected[1])

    def test_rejects_unsafe_hotkeys(self):
        for raw in ("Ctrl", "Alt", "Win", "Alt+Tab", "Ctrl+Alt+Delete", "Win+L", "Ctrl+Alt"):
            with self.subTest(raw=raw):
                self.assertFalse(validate_hotkey_format(raw).ok)

    def test_allows_supported_hotkeys(self):
        for raw in ("shift_r", "shift+win", "f8", "ctrl+alt+space", "ctrl+shift+d", "mouse_x1", "shift+mouse_x2"):
            with self.subTest(raw=raw):
                self.assertTrue(validate_hotkey_format(raw).ok)

    def test_rejects_bare_primary_mouse_buttons(self):
        self.assertFalse(validate_hotkey_format("mouse_left").ok)
        self.assertFalse(validate_hotkey_format("mouse_right").ok)

    def test_side_specific_modifier_matches_generic_event(self):
        self.assertTrue(token_matches("shift_r", {"shift"}))

    def test_russian_layout_letters_are_saved_as_latin_hotkeys(self):
        spec = parse_hotkey("Shift+\u042f")

        self.assertEqual(spec.canonical, "shift+z")
        self.assertEqual(spec.display, "Shift + Z")

    def test_keycode_vk_prefers_latin_physical_key(self):
        self.assertEqual(key_to_token(keyboard.KeyCode.from_vk(0x5A)), "z")
        self.assertEqual(key_to_token(keyboard.KeyCode.from_vk(0x41)), "a")

    def test_keycode_russian_char_falls_back_to_latin_layout(self):
        self.assertEqual(key_to_token(keyboard.KeyCode.from_char("\u044f")), "z")

    def test_mouse_side_buttons_are_hotkey_tokens(self):
        x1 = getattr(mouse.Button, "x1", None)
        x2 = getattr(mouse.Button, "x2", None)
        if x1 is not None:
            self.assertEqual(mouse_button_to_token(x1), "mouse_x1")
        if x2 is not None:
            self.assertEqual(mouse_button_to_token(x2), "mouse_x2")

    def test_default_hotkey_is_shift_win(self):
        self.assertEqual(AppConfig().hotkey, "shift+win")


if __name__ == "__main__":
    unittest.main()
