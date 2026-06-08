from __future__ import annotations

import tempfile
import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import sounddevice as sd

from .audio_devices import resolve_input_device
from .config import AppConfig


@dataclass(frozen=True)
class RecordingResult:
    path: Path
    duration_seconds: float
    rms: float


class AudioRecorder:
    def __init__(self, config: AppConfig):
        self._config = config
        self._lock = threading.RLock()
        self._chunks: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._started_at = 0.0

    def update_config(self, config: AppConfig) -> None:
        with self._lock:
            self._config = config

    def start(self) -> None:
        with self._lock:
            if self._stream:
                return
            self._chunks = []
            self._started_at = time.monotonic()
            device, fallback = resolve_input_device(self._config.microphone)
            try:
                self._stream = self._create_stream(device)
            except Exception:
                if not self._config.microphone or fallback:
                    raise
                self._stream = self._create_stream(None)
            self._stream.start()

    def stop(self) -> RecordingResult | None:
        with self._lock:
            stream = self._stream
            self._stream = None
        if stream:
            stream.stop()
            stream.close()

        with self._lock:
            chunks = list(self._chunks)
            self._chunks = []
            sample_rate = self._config.sample_rate

        if not chunks:
            return None

        audio = np.concatenate(chunks, axis=0)
        duration = float(len(audio) / sample_rate)
        rms = float(np.sqrt(np.mean(np.square(audio.reshape(-1)))))
        path = _write_wav(audio, sample_rate)
        return RecordingResult(path=path, duration_seconds=duration, rms=rms)

    def _callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        if status:
            # Keep recording; PortAudio status flags are often transient.
            pass
        with self._lock:
            if self._stream:
                self._chunks.append(indata.copy())

    def _create_stream(self, device: int | None) -> sd.InputStream:
        return sd.InputStream(
            samplerate=self._config.sample_rate,
            channels=1,
            callback=self._callback,
            dtype="float32",
            device=device,
        )


def _write_wav(audio: np.ndarray, sample_rate: int) -> Path:
    clipped = np.clip(audio.reshape(-1), -1.0, 1.0)
    pcm = (clipped * 32767).astype(np.int16)
    handle = tempfile.NamedTemporaryFile(prefix="voicetype-", suffix=".wav", delete=False)
    path = Path(handle.name)
    handle.close()
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm.tobytes())
    return path
