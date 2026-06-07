import unittest

from win_whisper_dictation.hotkey_spec import parse_hotkey, token_matches, validate_hotkey_format


class HotkeySpecTests(unittest.TestCase):
    def test_examples_are_normalized(self):
        cases = {
            "Right Shift": ("shift_r", "Right Shift"),
            "Ctrl + Alt + Space": ("ctrl+alt+space", "Ctrl + Alt + Space"),
            "F8": ("f8", "F8"),
            "Ctrl+Shift+D": ("ctrl+shift+d", "Ctrl + Shift + D"),
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
        for raw in ("shift_r", "f8", "ctrl+alt+space", "ctrl+shift+d"):
            with self.subTest(raw=raw):
                self.assertTrue(validate_hotkey_format(raw).ok)

    def test_side_specific_modifier_matches_generic_event(self):
        self.assertTrue(token_matches("shift_r", {"shift"}))


if __name__ == "__main__":
    unittest.main()
