import unittest

from win_whisper_dictation.postprocess import postprocess_text


class PostprocessTests(unittest.TestCase):
    def test_spoken_punctuation(self):
        self.assertEqual(postprocess_text("смотри двоеточие тест точка"), "смотри: тест.")

    def test_filename_commands(self):
        self.assertEqual(postprocess_text("config dot json"), "config.json")
        self.assertEqual(postprocess_text("src slash app underscore main dot py"), "src/app_main.py")


if __name__ == "__main__":
    unittest.main()
