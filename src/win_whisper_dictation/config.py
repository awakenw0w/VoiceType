from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from .hotkey_spec import parse_hotkey, validate_hotkey_format
from .i18n import normalize_language, normalize_local_model


@dataclass(frozen=True)
class AppConfig:
    hotkey: str = "shift_r"
    interface_language: str = "ru"
    provider: str = "local"
    model: str = "tiny"
    groq_model: str = "whisper-large-v3-turbo"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_api_key_env: str = "GROQ_API_KEY"
    language: str = ""
    device: str = "cpu"
    paste_mode: str = "clipboard"
    autostart: bool = False
    vad_filter: bool = True
    restore_clipboard: bool = True
    show_window_on_start: bool = True
    clipboard_restore_delay_seconds: float = 1.0
    sample_rate: int = 16000
    min_record_seconds: float = 0.35
    min_audio_rms: float = 0.0005
    compute_type_cpu: str = "int8"
    compute_type_cuda: str = "int8_float16"
    beam_size: int = 1
    enable_command_replacements: bool = True
    preload_model: bool = True


class ConfigManager:
    def __init__(self, path: Path | None = None):
        self.path = path or default_config_path()

    def load(self) -> AppConfig:
        if not self.path.exists():
            bundled = bundled_config_path()
            if bundled and bundled.exists():
                self.path.write_text(bundled.read_text(encoding="utf-8"), encoding="utf-8")
            else:
                config = AppConfig()
                self.save(config)
                return config

        data = tomllib.loads(self.path.read_text(encoding="utf-8"))
        values: dict[str, Any] = {}
        values.update(data.get("ui", {}))
        values.update(data.get("dictation", {}))
        values.update(data.get("transcription", {}))
        values.update(data.get("audio", {}))
        values.update(data.get("whisper", {}))
        values.update(data.get("windows", {}))

        config = AppConfig()
        for key in asdict(config):
            if key in values:
                config = replace(config, **{key: values[key]})

        try:
            normalized = parse_hotkey(config.hotkey).canonical
            if validate_hotkey_format(normalized).ok:
                config = replace(config, hotkey=normalized)
        except ValueError:
            config = replace(config, hotkey=AppConfig.hotkey)
        config = replace(
            config,
            interface_language=normalize_language(config.interface_language),
            model=normalize_local_model(config.model),
        )
        return config

    def save(self, config: AppConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(render_toml(config), encoding="utf-8")


def default_config_path() -> Path:
    env_path = os.environ.get("VOICETYPE_CONFIG") or os.environ.get("WIN_DICTATION_CONFIG")
    if env_path:
        return Path(env_path)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).with_name("config.toml")
    return Path.cwd() / "config.toml"


def bundled_config_path() -> Path | None:
    if not getattr(sys, "frozen", False):
        return None
    bundle_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return bundle_dir / "config.toml"


def render_toml(config: AppConfig) -> str:
    return "\n".join(
        [
            "[ui]",
            f'interface_language = "{_escape(normalize_language(config.interface_language))}"',
            "",
            "[dictation]",
            f'hotkey = "{_escape(config.hotkey)}"',
            f'paste_mode = "{_escape(config.paste_mode)}"',
            f"autostart = {_bool(config.autostart)}",
            f"restore_clipboard = {_bool(config.restore_clipboard)}",
            f"show_window_on_start = {_bool(config.show_window_on_start)}",
            f"clipboard_restore_delay_seconds = {float(config.clipboard_restore_delay_seconds)}",
            f"enable_command_replacements = {_bool(config.enable_command_replacements)}",
            f"preload_model = {_bool(config.preload_model)}",
            "",
            "[transcription]",
            f'provider = "{_escape(config.provider)}"',
            f'groq_model = "{_escape(config.groq_model)}"',
            f'groq_base_url = "{_escape(config.groq_base_url)}"',
            f'groq_api_key_env = "{_escape(config.groq_api_key_env)}"',
            "",
            "[whisper]",
            f'model = "{_escape(normalize_local_model(config.model))}"',
            f'language = "{_escape(config.language)}"',
            f'device = "{_escape(config.device)}"',
            f"vad_filter = {_bool(config.vad_filter)}",
            f'compute_type_cpu = "{_escape(config.compute_type_cpu)}"',
            f'compute_type_cuda = "{_escape(config.compute_type_cuda)}"',
            f"beam_size = {int(config.beam_size)}",
            "",
            "[audio]",
            f"sample_rate = {int(config.sample_rate)}",
            f"min_record_seconds = {float(config.min_record_seconds)}",
            f"min_audio_rms = {float(config.min_audio_rms)}",
            "",
        ]
    )


def _bool(value: bool) -> str:
    return "true" if value else "false"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
