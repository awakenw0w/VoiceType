import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from win_whisper_dictation.config import AppConfig, ConfigManager
from win_whisper_dictation.transcriber import GroqTranscriber, _extract_text


class TranscriptionProviderTests(unittest.TestCase):
    def test_config_round_trip_keeps_groq_provider(self):
        config = replace(AppConfig(), provider="groq", groq_model="whisper-large-v3")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.toml"
            manager = ConfigManager(path)
            manager.save(config)
            loaded = manager.load()

        self.assertEqual(loaded.provider, "groq")
        self.assertEqual(loaded.groq_model, "whisper-large-v3")

    def test_groq_requires_api_key_env(self):
        env_name = "WIN_DICTATION_TEST_MISSING_GROQ_KEY"
        os.environ.pop(env_name, None)
        config = replace(AppConfig(), groq_api_key_env=env_name)
        transcriber = GroqTranscriber(config)

        with self.assertRaisesRegex(RuntimeError, env_name):
            transcriber.transcribe(Path("does-not-need-to-exist.wav"))

    def test_extract_text_accepts_openai_response_shape(self):
        response = type("Response", (), {"text": " hello "})()
        self.assertEqual(_extract_text(response), "hello")


if __name__ == "__main__":
    unittest.main()
