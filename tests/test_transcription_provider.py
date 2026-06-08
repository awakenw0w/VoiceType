import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from win_whisper_dictation.config import AppConfig, ConfigManager
from win_whisper_dictation.transcriber import GroqTranscriber, LocalWhisperTranscriber, _extract_text


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

    def test_config_round_trip_keeps_interface_language(self):
        config = replace(AppConfig(), interface_language="en")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.toml"
            manager = ConfigManager(path)
            manager.save(config)
            loaded = manager.load()

        self.assertEqual(loaded.interface_language, "en")

    def test_config_normalizes_legacy_local_model(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.toml"
            path.write_text('[whisper]\nmodel = "medium"\n', encoding="utf-8")
            loaded = ConfigManager(path).load()

        self.assertEqual(loaded.model, "large-v3")

    def test_config_round_trip_keeps_microphone(self):
        config = replace(AppConfig(), microphone="Windows WASAPI::Studio Mic")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.toml"
            manager = ConfigManager(path)
            manager.save(config)
            loaded = manager.load()

        self.assertEqual(loaded.microphone, "Windows WASAPI::Studio Mic")

    def test_config_normalizes_gpu_device_alias(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.toml"
            path.write_text('[whisper]\ndevice = "gpu"\n', encoding="utf-8")
            loaded = ConfigManager(path).load()

        self.assertEqual(loaded.device, "cuda")

    def test_gpu_device_attempts_cpu_fallback(self):
        config = replace(AppConfig(), device="cuda", compute_type_cuda="int8_float16", compute_type_cpu="int8")
        transcriber = LocalWhisperTranscriber(config)

        self.assertEqual(transcriber._load_attempts(config), [("cuda", "int8_float16"), ("cpu", "int8")])

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
