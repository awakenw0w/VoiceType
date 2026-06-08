import unittest

from win_whisper_dictation.postprocess import postprocess_text


class PostprocessTests(unittest.TestCase):
    def test_spoken_punctuation(self):
        self.assertEqual(postprocess_text("смотри двоеточие тест точка"), "смотри: тест.")

    def test_filename_commands(self):
        self.assertEqual(postprocess_text("config dot json"), "config.json")
        self.assertEqual(postprocess_text("src slash app underscore main dot py"), "src/app_main.py")

    def test_auto_cleanup_handles_fillers_repeats_and_self_correction(self):
        self.assertEqual(postprocess_text("um meeting meeting today", auto_cleanup=True), "Meeting today")
        self.assertEqual(postprocess_text("meeting at 2 no at 3", auto_cleanup=True), "Meeting at 3.")

    def test_auto_cleanup_handles_russian_self_correction(self):
        text = "\u0432\u0441\u0442\u0440\u0435\u0447\u0430 \u0432 2 \u043d\u0435\u0442 \u0432 3"

        self.assertEqual(postprocess_text(text, auto_cleanup=True), "\u0412\u0441\u0442\u0440\u0435\u0447\u0430 \u0432 3.")

    def test_auto_cleanup_does_not_add_period_to_paths(self):
        self.assertEqual(postprocess_text("config dot json", auto_cleanup=True), "config.json")

    def test_formats_numbered_lists_when_explicit(self):
        text = "one buy milk two call Alex three send the report"

        self.assertEqual(
            postprocess_text(text, auto_cleanup=True, format_lists=True),
            "1. Buy milk\n2. Call Alex\n3. Send the report",
        )

    def test_formats_ordinal_lists_when_explicit(self):
        text = "first buy milk second call Alex third send the report"

        self.assertEqual(
            postprocess_text(text, format_lists=True),
            "1. Buy milk\n2. Call Alex\n3. Send the report",
        )

    def test_formats_russian_lists_when_explicit(self):
        text = (
            "\u043f\u0435\u0440\u0432\u043e\u0435 \u043a\u0443\u043f\u0438\u0442\u044c \u043c\u043e\u043b\u043e\u043a\u043e "
            "\u0432\u0442\u043e\u0440\u043e\u0435 \u043f\u043e\u0437\u0432\u043e\u043d\u0438\u0442\u044c \u0410\u043b\u0435\u043a\u0441\u0435\u044e "
            "\u0442\u0440\u0435\u0442\u044c\u0435 \u043e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u044c \u043e\u0442\u0447\u0451\u0442"
        )

        self.assertEqual(
            postprocess_text(text, format_lists=True),
            "1. \u041a\u0443\u043f\u0438\u0442\u044c \u043c\u043e\u043b\u043e\u043a\u043e\n"
            "2. \u041f\u043e\u0437\u0432\u043e\u043d\u0438\u0442\u044c \u0410\u043b\u0435\u043a\u0441\u0435\u044e\n"
            "3. \u041e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u044c \u043e\u0442\u0447\u0451\u0442",
        )

    def test_formats_embedded_russian_list_and_keeps_surrounding_text(self):
        text = (
            "\u0441\u043c\u043e\u0442\u0440\u0438 \u043f\u0435\u0440\u0432\u043e\u0435 \u0447\u0442\u043e \u043d\u0443\u0436\u043d\u043e \u043a\u0443\u043f\u0438\u0442\u044c "
            "\u043f\u0435\u0440\u0432\u043e\u0435 \u043c\u043e\u043b\u043e\u043a\u043e "
            "\u0432\u0442\u043e\u0440\u043e\u0435 \u043f\u043e\u0437\u0432\u043e\u043d\u0438\u0442\u044c \u0410\u043b\u0435\u043a\u0441\u0435\u044e "
            "\u0442\u0440\u0435\u0442\u044c\u0435 \u043e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u044c \u043e\u0442\u0447\u0451\u0442. "
            "\u041a\u0430\u043a \u044d\u0442\u043e \u0432\u0441\u0451 \u0441\u0434\u0435\u043b\u0430\u0435\u0448\u044c \u0431\u0443\u0434\u0435\u0448\u044c \u0441\u0432\u043e\u0431\u043e\u0434\u0435\u043d"
        )

        self.assertEqual(
            postprocess_text(text, format_lists=True),
            "\u0441\u043c\u043e\u0442\u0440\u0438 \u043f\u0435\u0440\u0432\u043e\u0435 \u0447\u0442\u043e \u043d\u0443\u0436\u043d\u043e \u043a\u0443\u043f\u0438\u0442\u044c\n"
            "1. \u041c\u043e\u043b\u043e\u043a\u043e\n"
            "2. \u041f\u043e\u0437\u0432\u043e\u043d\u0438\u0442\u044c \u0410\u043b\u0435\u043a\u0441\u0435\u044e\n"
            "3. \u041e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u044c \u043e\u0442\u0447\u0451\u0442\n"
            "\u041a\u0430\u043a \u044d\u0442\u043e \u0432\u0441\u0451 \u0441\u0434\u0435\u043b\u0430\u0435\u0448\u044c \u0431\u0443\u0434\u0435\u0448\u044c \u0441\u0432\u043e\u0431\u043e\u0434\u0435\u043d",
        )

    def test_formats_embedded_russian_list_without_punctuation_before_suffix(self):
        text = (
            "\u0441\u043c\u043e\u0442\u0440\u0438 \u043f\u0435\u0440\u0432\u043e\u0435 \u0447\u0442\u043e \u043d\u0443\u0436\u043d\u043e \u043a\u0443\u043f\u0438\u0442\u044c "
            "\u043f\u0435\u0440\u0432\u043e\u0435 \u043c\u043e\u043b\u043e\u043a\u043e "
            "\u0432\u0442\u043e\u0440\u043e\u0435 \u043f\u043e\u0437\u0432\u043e\u043d\u0438\u0442\u044c \u0410\u043b\u0435\u043a\u0441\u0435\u044e "
            "\u0442\u0440\u0435\u0442\u044c\u0435 \u043e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u044c \u043e\u0442\u0447\u0451\u0442 "
            "\u043a\u0430\u043a \u0432\u0441\u0435 \u044d\u0442\u043e \u0441\u0434\u0435\u043b\u0430\u0435\u0448\u044c \u0431\u0443\u0434\u0435\u0448\u044c \u0441\u0432\u043e\u0431\u043e\u0434\u0435\u043d"
        )

        self.assertEqual(
            postprocess_text(text, format_lists=True),
            "\u0441\u043c\u043e\u0442\u0440\u0438 \u043f\u0435\u0440\u0432\u043e\u0435 \u0447\u0442\u043e \u043d\u0443\u0436\u043d\u043e \u043a\u0443\u043f\u0438\u0442\u044c\n"
            "1. \u041c\u043e\u043b\u043e\u043a\u043e\n"
            "2. \u041f\u043e\u0437\u0432\u043e\u043d\u0438\u0442\u044c \u0410\u043b\u0435\u043a\u0441\u0435\u044e\n"
            "3. \u041e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u044c \u043e\u0442\u0447\u0451\u0442\n"
            "\u043a\u0430\u043a \u0432\u0441\u0435 \u044d\u0442\u043e \u0441\u0434\u0435\u043b\u0430\u0435\u0448\u044c \u0431\u0443\u0434\u0435\u0448\u044c \u0441\u0432\u043e\u0431\u043e\u0434\u0435\u043d",
        )

    def test_does_not_split_last_item_on_explanation_phrase(self):
        text = (
            "\u043f\u0435\u0440\u0432\u043e\u0435 \u043a\u0443\u043f\u0438\u0442\u044c \u043c\u043e\u043b\u043e\u043a\u043e "
            "\u0432\u0442\u043e\u0440\u043e\u0435 \u043e\u0431\u044a\u044f\u0441\u043d\u0438\u0442\u044c \u043a\u0430\u043a \u044d\u0442\u043e \u0440\u0430\u0431\u043e\u0442\u0430\u0435\u0442"
        )

        self.assertEqual(
            postprocess_text(text, format_lists=True),
            "1. \u041a\u0443\u043f\u0438\u0442\u044c \u043c\u043e\u043b\u043e\u043a\u043e\n"
            "2. \u041e\u0431\u044a\u044f\u0441\u043d\u0438\u0442\u044c \u043a\u0430\u043a \u044d\u0442\u043e \u0440\u0430\u0431\u043e\u0442\u0430\u0435\u0442",
        )

    def test_formats_embedded_english_list(self):
        text = "please do this first buy milk second call Alex third send the report. Then you are done"

        self.assertEqual(
            postprocess_text(text, format_lists=True),
            "please do this\n1. Buy milk\n2. Call Alex\n3. Send the report\nThen you are done",
        )

    def test_does_not_force_ordinary_text_into_list(self):
        text = "one day I will call Alex two days later"

        self.assertEqual(postprocess_text(text, format_lists=True), text)


if __name__ == "__main__":
    unittest.main()
