from __future__ import annotations

import os
import threading
from pathlib import Path

from .config import AppConfig


class DictationTranscriber:
    def __init__(self, config: AppConfig):
        self._config = config
        self._lock = threading.RLock()
        self._local = LocalWhisperTranscriber(config)
        self._groq = GroqTranscriber(config)

    @property
    def actual_device(self) -> str:
        with self._lock:
            provider = self._config.provider
        if provider == "groq":
            return "groq"
        return self._local.actual_device

    def update_config(self, config: AppConfig) -> None:
        with self._lock:
            self._config = config
        self._local.update_config(config)
        self._groq.update_config(config)

    def preload(self) -> str:
        with self._lock:
            provider = self._config.provider
        if provider == "groq":
            return "groq"
        return self._local.preload()

    def transcribe(self, audio_path: Path) -> str:
        with self._lock:
            provider = self._config.provider
        if provider == "groq":
            return self._groq.transcribe(audio_path)
        return self._local.transcribe(audio_path)


class GroqTranscriber:
    def __init__(self, config: AppConfig):
        self._config = config
        self._lock = threading.RLock()

    def update_config(self, config: AppConfig) -> None:
        with self._lock:
            self._config = config

    def transcribe(self, audio_path: Path) -> str:
        with self._lock:
            config = self._config

        api_key = os.environ.get(config.groq_api_key_env)
        if not api_key:
            raise RuntimeError(f"Переменная окружения {config.groq_api_key_env} не задана")

        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=config.groq_base_url)
        language = config.language.strip() or None
        request = {
            "model": config.groq_model,
        }
        if language:
            request["language"] = language

        with audio_path.open("rb") as audio_file:
            response = client.audio.transcriptions.create(file=audio_file, **request)

        return _extract_text(response)


class LocalWhisperTranscriber:
    def __init__(self, config: AppConfig):
        self._config = config
        self._lock = threading.RLock()
        self._model = None
        self._actual_device = ""
        self._cuda_disabled = False

    @property
    def actual_device(self) -> str:
        with self._lock:
            return self._actual_device

    def update_config(self, config: AppConfig) -> None:
        with self._lock:
            changed = (
                config.model != self._config.model
                or config.device != self._config.device
                or config.compute_type_cpu != self._config.compute_type_cpu
                or config.compute_type_cuda != self._config.compute_type_cuda
            )
            self._config = config
            if changed:
                self._model = None
                self._actual_device = ""
                self._cuda_disabled = False

    def preload(self) -> str:
        self._load_model()
        return self.actual_device

    def transcribe(self, audio_path: Path) -> str:
        try:
            return self._transcribe(audio_path)
        except Exception:
            with self._lock:
                should_retry_cpu = self._config.device == "auto" and self._actual_device == "cuda"
                if should_retry_cpu:
                    self._cuda_disabled = True
                    self._model = None
                    self._actual_device = ""
            if should_retry_cpu:
                return self._transcribe(audio_path)
            raise

    def _transcribe(self, audio_path: Path) -> str:
        model = self._load_model()
        with self._lock:
            language = self._config.language.strip() or None
            vad_filter = self._config.vad_filter
            beam_size = max(1, int(self._config.beam_size))

        segments, _info = model.transcribe(
            str(audio_path),
            language=language,
            vad_filter=vad_filter,
            beam_size=beam_size,
            condition_on_previous_text=False,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()

    def _load_model(self):
        with self._lock:
            if self._model is not None:
                return self._model
            config = self._config
            attempts = self._load_attempts(config)

        errors: list[str] = []
        from faster_whisper import WhisperModel

        for device, compute_type in attempts:
            try:
                model = WhisperModel(config.model, device=device, compute_type=compute_type)
                with self._lock:
                    self._model = model
                    self._actual_device = device
                return model
            except Exception as exc:
                errors.append(f"{device}/{compute_type}: {exc}")
                if config.device != "auto":
                    break
        raise RuntimeError("Не удалось загрузить модель faster-whisper: " + " | ".join(errors))

    def _load_attempts(self, config: AppConfig) -> list[tuple[str, str]]:
        if config.device == "cpu":
            return [("cpu", config.compute_type_cpu)]
        if config.device == "cuda":
            return [("cuda", config.compute_type_cuda)]
        attempts: list[tuple[str, str]] = []
        if not self._cuda_disabled:
            attempts.append(("cuda", config.compute_type_cuda))
        attempts.append(("cpu", config.compute_type_cpu))
        return attempts


def _extract_text(response) -> str:
    if isinstance(response, str):
        return response.strip()
    if isinstance(response, dict):
        return str(response.get("text", "")).strip()
    text = getattr(response, "text", "")
    if text:
        return str(text).strip()
    return str(response).strip()
