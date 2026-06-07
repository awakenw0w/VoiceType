from __future__ import annotations

import logging
import sys
import threading
from dataclasses import replace
from pathlib import Path
from tkinter import messagebox

from . import autostart
from .config import AppConfig, ConfigManager
from .hotkey_manager import HotkeyManager
from .hotkey_spec import parse_hotkey, validate_hotkey_system
from .i18n import t
from .postprocess import postprocess_text
from .recorder import AudioRecorder
from .settings_window import SettingsWindow
from .status import AppStatus
from .text_inserter import TextInserter, WindowInfo, get_foreground_window
from .transcriber import DictationTranscriber
from .tray import TrayController


LOG = logging.getLogger(__name__)
APP_NAME = "VoiceType"
APP_MUTEX_NAME = "Global\\VoiceTypeMutex"


class DictationApp:
    def __init__(self):
        self._single_instance = SingleInstance(APP_MUTEX_NAME)
        if self._single_instance.already_running:
            messagebox.showinfo(APP_NAME, t("ru", "already_running"))
            raise SystemExit(0)

        setup_logging()
        LOG.info("Starting %s", APP_NAME)
        self._config_manager = ConfigManager()
        self._config = self._config_manager.load()
        LOG.info(
            "Loaded config from %s: hotkey=%s provider=%s model=%s groq_model=%s device=%s",
            self._config_manager.path,
            self._config.hotkey,
            self._config.provider,
            self._config.model,
            self._config.groq_model,
            self._config.device,
        )
        self._status = AppStatus.IDLE
        self._paused = False
        self._recording = False
        self._busy = False
        self._target_window = WindowInfo(0, "")
        self._lock = threading.RLock()

        self._recorder = AudioRecorder(self._config)
        self._transcriber = DictationTranscriber(self._config)
        self._inserter = TextInserter(self._config)
        self._hotkeys = HotkeyManager(self._config.hotkey, self._recording_start, self._recording_stop)
        self._settings = SettingsWindow(self)
        self._tray = TrayController(self)

    @property
    def config(self) -> AppConfig:
        return self._config

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def status_text(self) -> str:
        with self._lock:
            return self._status.value

    def run(self) -> None:
        LOG.info("Starting tray icon")
        self._tray.run()

    def on_tray_ready(self) -> None:
        LOG.info("Tray ready, starting hotkey listener")
        self._hotkeys.start()
        self._set_status(AppStatus.IDLE)
        self._tray.notify(t(self._config.interface_language, "app_started", hotkey=parse_hotkey(self._config.hotkey).display))
        if self._config.preload_model:
            threading.Thread(target=self._preload_model, name="dictation-preload", daemon=True).start()
        if self._config.show_window_on_start:
            self.open_settings()

    def stop(self) -> None:
        LOG.info("Stopping app")
        self._hotkeys.stop()
        self._tray.stop()

    def toggle_pause(self) -> None:
        with self._lock:
            self._paused = not self._paused
            status = AppStatus.PAUSED if self._paused else AppStatus.IDLE
        self._set_status(status)

    def toggle_autostart(self) -> None:
        updated = replace(self._config, autostart=not self._config.autostart)
        self.apply_settings(updated)

    def reload_settings(self) -> None:
        self.apply_settings(self._config_manager.load(), save=False)

    def open_settings(self) -> None:
        self._settings.open()

    def begin_hotkey_capture(self, on_update, on_complete, on_error) -> None:
        self._hotkeys.begin_capture(on_update, on_complete, on_error)

    def cancel_hotkey_capture(self) -> None:
        self._hotkeys.cancel_capture()

    def apply_settings(self, config: AppConfig, save: bool = True) -> None:
        LOG.info(
            "Applying settings: hotkey=%s provider=%s model=%s groq_model=%s device=%s paste_mode=%s",
            config.hotkey,
            config.provider,
            config.model,
            config.groq_model,
            config.device,
            config.paste_mode,
        )
        result = validate_hotkey_system(config.hotkey)
        if not result.ok:
            raise ValueError(result.message)
        if config.paste_mode not in {"clipboard", "clipboard_then_typewrite", "typewrite"}:
            raise ValueError("Неподдерживаемый режим вставки")
        if config.provider not in {"local", "groq"}:
            raise ValueError("Провайдер должен быть local или groq")
        if config.device not in {"auto", "cpu", "cuda"}:
            raise ValueError("Устройство должно быть auto, cpu или cuda")

        autostart_changed = config.autostart != self._config.autostart
        with self._lock:
            self._config = config
            self._hotkeys.set_hotkey(config.hotkey)
            self._recorder.update_config(config)
            self._transcriber.update_config(config)
            self._inserter.update_config(config)
            if save:
                self._config_manager.save(config)

        if save or autostart_changed:
            autostart.set_autostart(config.autostart)
        self._tray.update_status(self._status)

    def _recording_start(self) -> None:
        LOG.info("Hotkey pressed")
        with self._lock:
            if self._paused or self._busy or self._recording:
                LOG.info("Recording ignored: paused=%s busy=%s recording=%s", self._paused, self._busy, self._recording)
                return
            self._recording = True
            self._target_window = get_foreground_window()
            LOG.info("Target window: hwnd=%s title=%r", self._target_window.hwnd, self._target_window.title)
        try:
            self._recorder.start()
            LOG.info("Recording started")
            self._set_status(AppStatus.RECORDING)
        except Exception:
            LOG.exception("Could not start recording")
            with self._lock:
                self._recording = False
            self._set_status(AppStatus.ERROR)

    def _recording_stop(self) -> None:
        LOG.info("Hotkey released")
        with self._lock:
            if not self._recording:
                return
            self._recording = False
            self._busy = True
        try:
            result = self._recorder.stop()
        except Exception:
            LOG.exception("Could not stop recording")
            with self._lock:
                self._busy = False
            self._set_status(AppStatus.ERROR)
            return

        if result is None or result.duration_seconds < self._config.min_record_seconds:
            LOG.info("Recording skipped: result=%s duration=%s", bool(result), result.duration_seconds if result else None)
            if result:
                _unlink_silent(result.path)
            with self._lock:
                self._busy = False
            self._set_status(AppStatus.IDLE)
            return
        if result.rms < self._config.min_audio_rms:
            LOG.info("Recording skipped: rms=%s threshold=%s", result.rms, self._config.min_audio_rms)
            _unlink_silent(result.path)
            with self._lock:
                self._busy = False
            self._set_status(AppStatus.IDLE)
            return

        threading.Thread(
            target=self._process_recording,
            args=(result.path,),
            name="dictation-transcribe",
            daemon=True,
        ).start()

    def _process_recording(self, path: Path) -> None:
        try:
            self._set_status(AppStatus.TRANSCRIBING)
            LOG.info("Transcribing %s", path)
            raw_text = self._transcriber.transcribe(path)
            text = postprocess_text(raw_text, enable_commands=self._config.enable_command_replacements)
            LOG.info("Transcription complete, raw_chars=%s chars=%s raw=%r final=%r", len(raw_text), len(text), raw_text, text)
            if text:
                self._set_status(AppStatus.PASTING)
                with self._lock:
                    target_hwnd = self._target_window.hwnd
                    target_title = self._target_window.title
                LOG.info("Inserting text into hwnd=%s title=%r", target_hwnd, target_title)
                self._inserter.insert(text, target_hwnd=target_hwnd)
                LOG.info("Text insert command sent")
                self._set_status(AppStatus.PASTED)
            else:
                self._set_status(AppStatus.IDLE)
        except Exception:
            LOG.exception("Dictation failed")
            self._set_status(AppStatus.ERROR)
        finally:
            _unlink_silent(path)
            with self._lock:
                self._busy = False
            if self._status in {AppStatus.PASTED, AppStatus.TRANSCRIBING, AppStatus.PASTING}:
                self._set_status(AppStatus.IDLE)

    def _preload_model(self) -> None:
        try:
            LOG.info("Preloading transcription model")
            device = self._transcriber.preload()
            LOG.info("Transcription model preloaded on %s", device)
        except Exception:
            LOG.exception("Could not preload transcription model")

    def _set_status(self, status: AppStatus) -> None:
        with self._lock:
            self._status = status
        self._tray.update_status(status)


def _unlink_silent(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


def main() -> None:
    try:
        DictationApp().run()
    except SystemExit:
        raise
    except Exception:
        setup_logging()
        LOG.exception("Fatal startup error")
        messagebox.showerror(
            APP_NAME,
            t("ru", "window_start_error", log=log_path()),
        )
        sys.exit(1)


class SingleInstance:
    def __init__(self, name: str):
        self.already_running = False
        self._handle = None
        if sys.platform != "win32":
            return
        import ctypes

        kernel32 = ctypes.windll.kernel32
        self._handle = kernel32.CreateMutexW(None, False, name)
        last_error = kernel32.GetLastError()
        self.already_running = last_error == 183

    def __del__(self):
        if self._handle and sys.platform == "win32":
            try:
                import ctypes

                ctypes.windll.kernel32.CloseHandle(self._handle)
            except Exception:
                pass


def setup_logging() -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[
            logging.FileHandler(path, encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )


def log_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).with_name("VoiceType.log")
    return Path.cwd() / "VoiceType.log"
