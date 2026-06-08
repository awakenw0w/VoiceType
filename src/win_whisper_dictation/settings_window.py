from __future__ import annotations

import ctypes
import os
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from dataclasses import replace
from pathlib import Path

import numpy as np
import sounddevice as sd
from PIL import Image, ImageDraw, ImageFilter, ImageTk

from .audio_devices import SYSTEM_MICROPHONE_ID, list_input_devices, resolve_input_device
from .config import AppConfig
from .hotkey_spec import parse_hotkey
from .i18n import (
    groq_model_labels,
    language_labels,
    local_model_labels,
    normalize_language,
    normalize_local_model,
    normalize_processing_device,
    processing_device_hint,
    processing_device_labels,
    provider_labels,
    status_label,
    t,
)
from .status import AppStatus
from .transcriber import gpu_available


APP_NAME = "VoiceType"
WINDOW_WIDTH = 768
WINDOW_HEIGHT = 626
AA_SCALE = 4

COLORS = {
    "shell": "#fbfaf8",
    "header": "#fffefd",
    "footer": "#fffefd",
    "card": "#ffffff",
    "field": "#f4f1ee",
    "field_hover": "#eee9e4",
    "border": "#e8e3dc",
    "border_soft": "#d8cfc3",
    "text": "#1b1c1c",
    "muted": "#5a5147",
    "caption": "#756b5f",
    "accent": "#d4bd92",
    "accent_soft": "#eadbc1",
    "accent_hover": "#dfc99f",
    "accent_text": "#251c0e",
    "gold_deep": "#8a7652",
    "graphite": "#2a2926",
    "black": "#1b1c1c",
    "white": "#fbf9f9",
    "pill": "#f5f0e8",
}


class SettingsWindow:
    def __init__(self, app):
        self._app = app
        self._thread: threading.Thread | None = None
        self._root: tk.Tk | None = None
        self._images: dict[str, tk.PhotoImage] = {}
        self._stop_microphone_test = None

    def open(self) -> None:
        if self._root:
            self._root.after(0, self._focus)
            return
        self._thread = threading.Thread(target=self._run, name="settings-window", daemon=True)
        self._thread.start()

    def _focus(self) -> None:
        if self._root:
            self._root.deiconify()
            self._root.lift()
            self._root.focus_force()
            self._root.after(40, lambda: _enable_taskbar_icon(self._root))

    def _run(self) -> None:
        config = self._app.config
        root = tk.Tk()
        self._root = root
        root.title(APP_NAME)
        root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        root.minsize(WINDOW_WIDTH, WINDOW_HEIGHT)
        root.maxsize(WINDOW_WIDTH, WINDOW_HEIGHT)
        root.resizable(False, False)
        root.overrideredirect(True)
        root.configure(bg=COLORS["shell"])
        root.protocol("WM_DELETE_WINDOW", lambda: self._hide(root))

        _load_private_font(Path("fonts") / "ArchivoBlack-Regular.ttf")
        _load_private_font(Path("fonts") / "Manrope-Variable.ttf")
        fonts = _make_fonts(root)
        self._load_assets(root)
        self._apply_window_icon(root)
        _configure_borderless(root)

        hotkey_var = tk.StringVar(value=parse_hotkey(config.hotkey).display)
        hotkey_canonical = tk.StringVar(value=config.hotkey)
        status_var = tk.StringVar(value="")
        runtime_status_var = tk.StringVar(value="")
        hotkey_capture_active_var = tk.BooleanVar(value=False)
        interface_language_var = tk.StringVar()
        current_language = tk.StringVar(value=normalize_language(config.interface_language))
        provider_var = tk.StringVar(value=config.provider)
        groq_model_var = tk.StringVar(value=config.groq_model)
        groq_key_status_var = tk.StringVar(value=_groq_key_status(config))
        model_var = tk.StringVar(value=normalize_local_model(config.model))
        autostart_var = tk.BooleanVar(value=_autostart_state(config))
        auto_cleanup_var = tk.BooleanVar(value=bool(config.auto_cleanup))
        format_lists_var = tk.BooleanVar(value=bool(config.format_lists))
        microphone_var = tk.StringVar()
        microphone_status_var = tk.StringVar(value="")
        microphone_level_var = tk.DoubleVar(value=0.0)
        processing_device_var = tk.StringVar()
        processing_hint_var = tk.StringVar()
        stats_value_vars = {
            "words": tk.StringVar(value="0"),
            "wpm": tk.StringVar(value="0"),
            "streak": tk.StringVar(value="0"),
            "sessions": tk.StringVar(value="0"),
        }
        current_view = tk.StringVar(value="main")
        provider_trace_id: str | None = None
        main_trace_ids: list[tuple[tk.Variable, str]] = []
        microphone_trace_id: str | None = None
        processing_trace_id: str | None = None
        language_trace_id: str | None = None
        cleanup_trace_ids: list[tuple[tk.Variable, str]] = []
        microphone_label_to_id: dict[str, str] = {}
        suppress_live_apply = False

        shell = tk.Frame(
            root,
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT,
            bg=COLORS["shell"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
        )
        shell.place(x=0, y=0)

        header = tk.Frame(shell, width=766, height=97, bg=COLORS["header"])
        header.place(x=1, y=1)
        tk.Frame(shell, width=766, height=1, bg=COLORS["border"]).place(x=1, y=98)

        content = tk.Frame(shell, width=766, height=444, bg=COLORS["shell"])
        content.place(x=1, y=99)

        footer = tk.Frame(shell, width=766, height=83, bg=COLORS["footer"])
        footer.place(x=1, y=543)
        tk.Frame(shell, width=766, height=1, bg=COLORS["border"]).place(x=1, y=542)

        def language() -> str:
            return normalize_language(current_language.get())

        def text_value(key: str, **kwargs) -> str:
            return t(language(), key, **kwargs)

        def provider_value(default: str = "local") -> str:
            return _value_for_any((provider_labels("ru"), provider_labels("en")), provider_var.get(), default)

        def groq_model_value(default: str = "whisper-large-v3-turbo") -> str:
            return _value_for_any((groq_model_labels("ru"), groq_model_labels("en")), groq_model_var.get(), default)

        def local_model_value(default: str = "tiny") -> str:
            value = _value_for_any((local_model_labels("ru"), local_model_labels("en")), model_var.get(), default)
            return normalize_local_model(value)

        def selected_language(default: str | None = None) -> str:
            return _value_for_any((language_labels("ru"), language_labels("en")), interface_language_var.get(), default or language())

        def processing_device_value(default: str = "cpu") -> str:
            value = _value_for_any((processing_device_labels("ru"), processing_device_labels("en")), processing_device_var.get(), default)
            return normalize_processing_device(value)

        def microphone_choices() -> tuple[tuple[str, ...], dict[str, str], bool, bool, str]:
            labels = {text_value("microphone_system"): SYSTEM_MICROPHONE_ID}
            aliases: dict[str, tuple[str, ...]] = {text_value("microphone_system"): ()}
            devices = list_input_devices()
            for device in devices:
                label = device.display_name
                if label in labels:
                    label = f"{label} #{device.index}"
                labels[label] = device.id
                aliases[label] = device.aliases
            values = tuple(labels.keys())
            selected_id = str(self._app.config.microphone or "").strip()
            selected_label = values[0]
            selected_missing = False
            if selected_id:
                matched_label = next(
                    (
                        label
                        for label, value in labels.items()
                        if selected_id == value or selected_id in aliases.get(label, ())
                    ),
                    None,
                )
                selected_missing = matched_label is None
                if matched_label:
                    selected_label = matched_label
            return values, labels, not devices, selected_missing, selected_label

        def selected_microphone_id() -> str:
            return microphone_label_to_id.get(microphone_var.get(), SYSTEM_MICROPHONE_ID)

        def sync_display_variables() -> None:
            lang = language()
            nonlocal microphone_label_to_id
            current_config_snapshot = self._app.config
            provider_var.set(_label_for(provider_labels(lang), provider_value(current_config_snapshot.provider)))
            groq_model_var.set(_label_for(groq_model_labels(lang), groq_model_value(current_config_snapshot.groq_model)))
            model_var.set(_label_for(local_model_labels(lang), local_model_value(current_config_snapshot.model)))
            autostart_var.set(bool(current_config_snapshot.autostart))
            auto_cleanup_var.set(bool(current_config_snapshot.auto_cleanup))
            format_lists_var.set(bool(current_config_snapshot.format_lists))
            interface_language_var.set(_label_for(language_labels(lang), lang))
            processing_device_var.set(_label_for(processing_device_labels(lang), processing_device_value(current_config_snapshot.device)))
            processing_hint_var.set(processing_device_hint(lang, processing_device_value(current_config_snapshot.device)))
            values, microphone_label_to_id, no_devices, missing, selected_label = microphone_choices()
            microphone_var.set(selected_label)
            if missing:
                microphone_status_var.set(text_value("selected_microphone_fallback"))
            elif no_devices:
                microphone_status_var.set(text_value("no_input_devices"))
            else:
                microphone_status_var.set(text_value("microphone_ready"))

        def sync_stats_variables() -> None:
            stats = self._app.stats
            stats_value_vars["words"].set(_format_int(stats.words_dictated))
            stats_value_vars["wpm"].set(_format_number(stats.words_per_minute))
            stats_value_vars["streak"].set(_format_int(stats.current_streak))
            stats_value_vars["sessions"].set(_format_int(stats.dictation_sessions))

        def clear_main_trace() -> None:
            nonlocal provider_trace_id
            if provider_trace_id:
                try:
                    provider_var.trace_remove("write", provider_trace_id)
                except tk.TclError:
                    pass
                provider_trace_id = None
            while main_trace_ids:
                variable, trace_id = main_trace_ids.pop()
                try:
                    variable.trace_remove("write", trace_id)
                except tk.TclError:
                    pass

        def clear_settings_traces() -> None:
            nonlocal microphone_trace_id, processing_trace_id, language_trace_id
            for variable, trace_id in (
                (microphone_var, microphone_trace_id),
                (processing_device_var, processing_trace_id),
                (interface_language_var, language_trace_id),
            ):
                if trace_id:
                    try:
                        variable.trace_remove("write", trace_id)
                    except tk.TclError:
                        pass
            microphone_trace_id = None
            processing_trace_id = None
            language_trace_id = None
            while cleanup_trace_ids:
                variable, trace_id = cleanup_trace_ids.pop()
                try:
                    variable.trace_remove("write", trace_id)
                except tk.TclError:
                    pass

        def clear_frame(frame: tk.Frame) -> None:
            for child in frame.winfo_children():
                child.destroy()

        def render_header() -> None:
            clear_frame(header)
            BrandMark(header, self._images.get("brand_mark")).place(x=32, y=25)
            tk.Label(
                header,
                text=APP_NAME,
                bg=COLORS["header"],
                fg=COLORS["text"],
                font=fonts["title"],
            ).place(x=88, y=22)
            tk.Label(
                header,
                text=text_value("tagline"),
                bg=COLORS["header"],
                fg=COLORS["muted"],
                font=fonts["caption_bold"],
            ).place(x=89, y=58)
            StatusPill(header, runtime_status_var, fonts["status"], width=170).place(x=488, y=31)
            _bind_drag_tree(header, root, skip_types=(WindowButton,))

        def apply_live_settings() -> None:
            if suppress_live_apply:
                return
            try:
                new_config = current_config()
                self._app.apply_settings(new_config, save=False)
                groq_key_status_var.set(_groq_key_status(new_config))
                if new_config.device == "cuda" and not gpu_available():
                    status_var.set(text_value("processing_gpu_unavailable"))
            except Exception as exc:
                status_var.set(f"{text_value('settings_error')}: {exc}")

        def render_main() -> None:
            nonlocal provider_trace_id, suppress_live_apply
            current_view.set("main")
            suppress_live_apply = True
            stop_microphone_test()
            clear_main_trace()
            clear_settings_traces()
            sync_display_variables()
            render_header()
            clear_frame(content)
            clear_frame(footer)

            hotkey_card = Card(content, 702, 102, radius=18)
            hotkey_card.place(x=32, y=32)
            tk.Label(
                hotkey_card,
                text=text_value("hotkey"),
                bg=COLORS["card"],
                fg=COLORS["text"],
                font=fonts["section"],
            ).place(x=25, y=22)
            tk.Label(
                hotkey_card,
                text=text_value("hotkey_subtitle"),
                bg=COLORS["card"],
                fg=COLORS["caption"],
                font=fonts["body_bold"],
            ).place(x=25, y=56)
            HotkeyField(
                hotkey_card,
                hotkey_var,
                fonts["body"],
                self._images.get("keyboard"),
                width=250,
                height=44,
            ).place(x=292, y=24)
            RoundedButton(
                hotkey_card,
                text=text_value("change"),
                command=lambda: record_hotkey(),
                font=fonts["button"],
                width=122,
                height=42,
                fill=COLORS["accent_soft"],
                hover_fill=COLORS["accent_hover"],
                active_fill="#cba976",
                active_var=hotkey_capture_active_var,
                fg=COLORS["accent_text"],
                radius=11,
            ).place(x=554, y=25)

            recognition_card = Card(content, 339, 253, radius=18)
            recognition_card.place(x=32, y=158)
            IconLabel(
                recognition_card,
                text_value("recognition"),
                fonts["section"],
                self._images.get("recognition"),
                icon_size=20,
            ).place(x=25, y=25)
            RadioOption(
                recognition_card,
                provider_var,
                value=provider_labels(language())["groq"],
                title=text_value("provider_groq"),
                subtitle=text_value("provider_groq_subtitle"),
                fonts=fonts,
            ).place(x=25, y=69)
            RadioOption(
                recognition_card,
                provider_var,
                value=provider_labels(language())["local"],
                title=text_value("provider_local"),
                subtitle=text_value("provider_local_subtitle"),
                fonts=fonts,
            ).place(x=25, y=121)

            groq_model_card = Card(content, 339, 160, radius=18)
            _build_model_card(
                groq_model_card,
                title=text_value("groq_model"),
                variable=groq_model_var,
                values=tuple(groq_model_labels(language()).values()),
                status_var=None,
                fonts=fonts,
                images=self._images,
            )

            local_model_card = Card(content, 339, 160, radius=18)
            _build_model_card(
                local_model_card,
                title=text_value("local_model"),
                variable=model_var,
                values=tuple(local_model_labels(language()).values()),
                status_var=None,
                fonts=fonts,
                images=self._images,
            )

            autostart_card = Card(content, 339, 90, radius=18)
            autostart_card.place(x=395, y=342)
            IconLabel(
                autostart_card,
                text_value("launch_with_windows"),
                fonts["button"],
                self._images.get("power"),
                icon_size=20,
                lines=2,
            ).place(x=25, y=25)
            ToggleSwitch(autostart_card, autostart_var).place(x=258, y=31)

            def update_model_fields(*_args) -> None:
                provider = provider_value("local")
                if provider == "groq":
                    local_model_card.place_forget()
                    groq_model_card.place(x=395, y=158)
                else:
                    groq_model_card.place_forget()
                    local_model_card.place(x=395, y=158)
                apply_live_settings()

            provider_trace_id = provider_var.trace_add("write", update_model_fields)
            main_trace_ids.extend(
                [
                    (groq_model_var, groq_model_var.trace_add("write", lambda *_: apply_live_settings())),
                    (model_var, model_var.trace_add("write", lambda *_: apply_live_settings())),
                    (autostart_var, autostart_var.trace_add("write", lambda *_: apply_live_settings())),
                ]
            )
            update_model_fields()

            RoundedButton(
                footer,
                text=text_value("exit"),
                command=lambda: exit_app(root),
                font=fonts["body"],
                width=72,
                height=38,
                fill=COLORS["white"],
                hover_fill="#f7f2ea",
                fg=COLORS["text"],
                border=COLORS["border_soft"],
                radius=11,
            ).place(x=32, y=23)
            RoundedButton(
                footer,
                text=text_value("settings"),
                command=lambda: render_settings(),
                font=fonts["body"],
                width=120,
                height=38,
                fill=COLORS["white"],
                hover_fill="#f7f2ea",
                fg=COLORS["text"],
                border=COLORS["border_soft"],
                radius=11,
            ).place(x=114, y=23)
            tk.Label(
                footer,
                textvariable=status_var,
                bg=COLORS["footer"],
                fg=COLORS["caption"],
                font=fonts["caption"],
                anchor="w",
                wraplength=250,
            ).place(x=250, y=25, width=240, height=38)
            RoundedButton(
                footer,
                text=text_value("hide"),
                command=lambda: self._hide(root),
                font=fonts["button"],
                width=104,
                height=42,
                fill=COLORS["footer"],
                hover_fill=COLORS["field"],
                fg=COLORS["text"],
                border=COLORS["border_soft"],
                radius=11,
            ).place(x=495, y=21)
            RoundedButton(
                footer,
                text=text_value("save"),
                command=lambda: save(),
                font=fonts["button"],
                width=123,
                height=42,
                fill=COLORS["black"],
                hover_fill="#33312e",
                fg=COLORS["white"],
                radius=11,
                shadow=True,
            ).place(x=611, y=21)
            suppress_live_apply = False

        microphone_test_lock = threading.RLock()
        microphone_test_state = {
            "stream": None,
            "active": False,
            "target": 0.0,
            "current": 0.0,
            "peak": 0.0,
            "deadline": 0.0,
            "after": None,
        }

        def stop_microphone_test() -> None:
            with microphone_test_lock:
                after_id = microphone_test_state.get("after")
                microphone_test_state["after"] = None
                microphone_test_state["active"] = False
                stream = microphone_test_state.get("stream")
                microphone_test_state["stream"] = None
            if after_id:
                try:
                    root.after_cancel(after_id)
                except tk.TclError:
                    pass
            if stream:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
            microphone_level_var.set(0.0)

        def start_microphone_test() -> None:
            stop_microphone_test()
            selected_id = selected_microphone_id()
            device, fallback = resolve_input_device(selected_id)

            def callback(indata: np.ndarray, frames: int, time_info, status) -> None:
                level = float(np.sqrt(np.mean(np.square(indata.reshape(-1)))))
                normalized = min(1.0, level * 22.0)
                with microphone_test_lock:
                    microphone_test_state["target"] = max(float(microphone_test_state["target"]), normalized)
                    microphone_test_state["peak"] = max(float(microphone_test_state["peak"]), normalized)

            try:
                stream = sd.InputStream(
                    samplerate=self._app.config.sample_rate,
                    channels=1,
                    dtype="float32",
                    callback=callback,
                    device=device,
                )
            except Exception:
                if not selected_id or fallback:
                    microphone_status_var.set(text_value("microphone_unavailable"))
                    return
                try:
                    stream = sd.InputStream(
                        samplerate=self._app.config.sample_rate,
                        channels=1,
                        dtype="float32",
                        callback=callback,
                        device=None,
                    )
                    fallback = True
                except Exception:
                    microphone_status_var.set(text_value("microphone_unavailable"))
                    return

            try:
                stream.start()
            except Exception:
                try:
                    stream.close()
                except Exception:
                    pass
                microphone_status_var.set(text_value("microphone_unavailable"))
                return

            with microphone_test_lock:
                microphone_test_state.update(
                    {
                        "stream": stream,
                        "active": True,
                        "target": 0.0,
                        "current": 0.0,
                        "peak": 0.0,
                        "deadline": time.monotonic() + 4.0,
                    }
                )
            microphone_status_var.set(text_value("selected_microphone_fallback") if fallback else text_value("status_listening"))

            def tick() -> None:
                with microphone_test_lock:
                    if not microphone_test_state["active"]:
                        return
                    current = float(microphone_test_state["current"])
                    target = float(microphone_test_state["target"])
                    current = current + (target - current) * 0.32
                    microphone_test_state["current"] = current
                    microphone_test_state["target"] = target * 0.72
                    peak = float(microphone_test_state["peak"])
                    done = time.monotonic() >= float(microphone_test_state["deadline"])

                microphone_level_var.set(current)
                if done:
                    stop_microphone_test()
                    microphone_status_var.set(text_value("microphone_ready") if peak >= 0.04 else text_value("no_input_detected"))
                    return
                with microphone_test_lock:
                    microphone_test_state["after"] = root.after(33, tick)

            tick()

        self._stop_microphone_test = stop_microphone_test

        def render_settings() -> None:
            nonlocal microphone_trace_id, processing_trace_id, language_trace_id, microphone_label_to_id, suppress_live_apply
            current_view.set("settings")
            suppress_live_apply = True
            stop_microphone_test()
            clear_main_trace()
            clear_settings_traces()
            sync_display_variables()
            render_header()
            clear_frame(content)
            clear_frame(footer)
            settings_body = _make_scroll_area(content, width=766, height=444, content_height=728)

            language_card = Card(settings_body, 702, 96, radius=18)
            language_card.place(x=32, y=18)
            tk.Label(
                language_card,
                text=text_value("settings"),
                bg=COLORS["card"],
                fg=COLORS["text"],
                font=fonts["section"],
            ).place(x=25, y=18)
            tk.Label(
                language_card,
                text=text_value("interface_language"),
                bg=COLORS["card"],
                fg=COLORS["text"],
                font=fonts["button"],
            ).place(x=25, y=55)
            SelectBox(
                language_card,
                interface_language_var,
                tuple(language_labels(language()).values()),
                fonts["body"],
                self._images.get("chevron"),
                width=270,
                height=48,
            ).place(x=397, y=24)

            audio_card = Card(settings_body, 702, 186, radius=18)
            audio_card.place(x=32, y=126)
            tk.Label(
                audio_card,
                text=text_value("audio"),
                bg=COLORS["card"],
                fg=COLORS["text"],
                font=fonts["section"],
            ).place(x=25, y=18)
            tk.Label(
                audio_card,
                text=text_value("microphone"),
                bg=COLORS["card"],
                fg=COLORS["text"],
                font=fonts["button"],
            ).place(x=25, y=58)
            values, microphone_label_to_id, no_devices, missing, selected_label = microphone_choices()
            if microphone_var.get() not in values:
                microphone_var.set(selected_label)
            if missing:
                microphone_status_var.set(text_value("selected_microphone_fallback"))
            elif no_devices:
                microphone_status_var.set(text_value("no_input_devices"))
            SelectBox(
                audio_card,
                microphone_var,
                values,
                fonts["body"],
                self._images.get("chevron"),
                width=340,
                height=48,
            ).place(x=166, y=48)
            RoundedButton(
                audio_card,
                text=text_value("microphone_test"),
                command=lambda: start_microphone_test(),
                font=fonts["button"],
                width=152,
                height=42,
                fill=COLORS["accent_soft"],
                hover_fill=COLORS["accent_hover"],
                fg=COLORS["accent_text"],
                radius=11,
            ).place(x=526, y=51)
            LevelMeter(audio_card, microphone_level_var, width=340, height=24).place(x=166, y=113)
            tk.Label(
                audio_card,
                textvariable=microphone_status_var,
                bg=COLORS["card"],
                fg=COLORS["caption"],
                font=fonts["caption"],
                anchor="w",
                wraplength=610,
            ).place(x=25, y=148, width=650, height=20)

            processing_card = Card(settings_body, 702, 116, radius=18)
            processing_card.place(x=32, y=324)
            tk.Label(
                processing_card,
                text=text_value("local_processing"),
                bg=COLORS["card"],
                fg=COLORS["text"],
                font=fonts["section"],
            ).place(x=25, y=18)
            tk.Label(
                processing_card,
                text=text_value("processing_device"),
                bg=COLORS["card"],
                fg=COLORS["text"],
                font=fonts["button"],
            ).place(x=25, y=59)
            SelectBox(
                processing_card,
                processing_device_var,
                tuple(processing_device_labels(language()).values()),
                fonts["body"],
                self._images.get("chevron"),
                width=270,
                height=48,
            ).place(x=397, y=31)
            tk.Label(
                processing_card,
                textvariable=processing_hint_var,
                bg=COLORS["card"],
                fg=COLORS["caption"],
                font=fonts["caption"],
                anchor="w",
                wraplength=650,
            ).place(x=25, y=88, width=650, height=18)

            cleanup_card = Card(settings_body, 702, 132, radius=18)
            cleanup_card.place(x=32, y=452)
            tk.Label(
                cleanup_card,
                text=text_value("text_cleanup"),
                bg=COLORS["card"],
                fg=COLORS["text"],
                font=fonts["section"],
            ).place(x=25, y=18)
            tk.Label(
                cleanup_card,
                text=text_value("auto_cleanup"),
                bg=COLORS["card"],
                fg=COLORS["text"],
                font=fonts["button"],
            ).place(x=25, y=54)
            tk.Label(
                cleanup_card,
                text=text_value("auto_cleanup_subtitle"),
                bg=COLORS["card"],
                fg=COLORS["caption"],
                font=fonts["caption"],
                anchor="w",
            ).place(x=25, y=77, width=540, height=18)
            ToggleSwitch(cleanup_card, auto_cleanup_var).place(x=610, y=53)
            tk.Label(
                cleanup_card,
                text=text_value("format_lists"),
                bg=COLORS["card"],
                fg=COLORS["text"],
                font=fonts["button"],
            ).place(x=25, y=100)
            tk.Label(
                cleanup_card,
                text=text_value("format_lists_subtitle"),
                bg=COLORS["card"],
                fg=COLORS["caption"],
                font=fonts["caption"],
                anchor="w",
            ).place(x=255, y=101, width=330, height=18)
            ToggleSwitch(cleanup_card, format_lists_var).place(x=610, y=96)

            stats_card = Card(settings_body, 702, 132, radius=18)
            stats_card.place(x=32, y=596)
            tk.Label(
                stats_card,
                text=text_value("statistics"),
                bg=COLORS["card"],
                fg=COLORS["text"],
                font=fonts["section"],
            ).place(x=25, y=18)
            sync_stats_variables()
            _place_stat(stats_card, text_value("stat_words_dictated"), stats_value_vars["words"], fonts, x=25, y=56)
            _place_stat(stats_card, text_value("stat_words_per_minute"), stats_value_vars["wpm"], fonts, x=200, y=56)
            _place_stat(stats_card, text_value("stat_current_streak"), stats_value_vars["streak"], fonts, x=375, y=56)
            _place_stat(stats_card, text_value("stat_dictation_sessions"), stats_value_vars["sessions"], fonts, x=550, y=56)

            def update_microphone_status(*_args) -> None:
                stop_microphone_test()
                if no_devices:
                    microphone_status_var.set(text_value("no_input_devices"))
                else:
                    microphone_status_var.set(text_value("microphone_ready"))
                microphone_level_var.set(0.0)
                apply_live_settings()

            def update_processing_hint(*_args) -> None:
                processing_hint_var.set(processing_device_hint(language(), processing_device_value("cpu")))
                apply_live_settings()

            def update_language_choice(*_args) -> None:
                selected = normalize_language(selected_language())
                current_language.set(selected)
                apply_live_settings()
                root.after(0, render_settings)

            language_trace_id = interface_language_var.trace_add("write", update_language_choice)
            microphone_trace_id = microphone_var.trace_add("write", update_microphone_status)
            processing_trace_id = processing_device_var.trace_add("write", update_processing_hint)
            cleanup_trace_ids.extend(
                [
                    (auto_cleanup_var, auto_cleanup_var.trace_add("write", lambda *_: apply_live_settings())),
                    (format_lists_var, format_lists_var.trace_add("write", lambda *_: apply_live_settings())),
                ]
            )
            update_processing_hint()

            TextButton(
                footer,
                text=text_value("back"),
                command=lambda: render_main(),
                font=fonts["body"],
            ).place(x=32, y=24)
            tk.Label(
                footer,
                textvariable=status_var,
                bg=COLORS["footer"],
                fg=COLORS["caption"],
                font=fonts["caption"],
                anchor="w",
                wraplength=360,
            ).place(x=130, y=25, width=355, height=38)
            RoundedButton(
                footer,
                text=text_value("save"),
                command=lambda: save(),
                font=fonts["button"],
                width=123,
                height=42,
                fill=COLORS["black"],
                hover_fill="#33312e",
                fg=COLORS["white"],
                radius=11,
                shadow=True,
            ).place(x=611, y=21)
            settings_body._refresh_mousewheel_bindings()
            suppress_live_apply = False

        def current_config(hotkey: str | None = None, interface_language: str | None = None) -> AppConfig:
            return replace(
                self._app.config,
                hotkey=hotkey or hotkey_canonical.get(),
                interface_language=interface_language or selected_language(),
                provider=provider_value("local"),
                groq_model=groq_model_value("whisper-large-v3-turbo"),
                model=local_model_value("tiny"),
                device=processing_device_value("cpu"),
                microphone=selected_microphone_id(),
                autostart=bool(autostart_var.get()),
                auto_cleanup=bool(auto_cleanup_var.get()),
                format_lists=bool(format_lists_var.get()),
            )

        def record_hotkey() -> None:
            hotkey_capture_active_var.set(True)
            status_var.set(text_value("press_hotkey"))

            def update(display: str) -> None:
                root.after(0, lambda: hotkey_var.set(display))

            def complete(canonical: str, display: str) -> None:
                def apply() -> None:
                    previous_canonical = hotkey_canonical.get()
                    previous_display = hotkey_var.get()
                    hotkey_canonical.set(canonical)
                    hotkey_var.set(display)
                    try:
                        new_config = current_config(hotkey=canonical)
                        self._app.apply_settings(new_config, save=False)
                        groq_key_status_var.set(_groq_key_status(new_config))
                        status_var.set(text_value("hotkey_applied", hotkey=display))
                    except Exception as exc:
                        hotkey_canonical.set(previous_canonical)
                        hotkey_var.set(previous_display)
                        status_var.set(f"{text_value('hotkey_error')}: {exc}")
                    finally:
                        hotkey_capture_active_var.set(False)

                root.after(0, apply)

            def error(message: str) -> None:
                def apply() -> None:
                    hotkey_capture_active_var.set(False)
                    status_var.set(message)

                root.after(0, apply)

            self._app.begin_hotkey_capture(update, complete, error)

        def save() -> None:
            try:
                new_config = current_config()
                self._app.apply_settings(new_config)
                groq_key_status_var.set(_groq_key_status(new_config))
                current_language.set(normalize_language(new_config.interface_language))
                status_var.set(text_value("saved"))
                if current_view.get() == "settings":
                    render_settings()
                else:
                    render_main()
            except Exception as exc:
                status_var.set(f"{text_value('settings_error')}: {exc}")

        def apply_settings(save_changes: bool) -> None:
            try:
                selected = selected_language()
                new_config = current_config(interface_language=selected)
                self._app.apply_settings(new_config, save=save_changes)
                current_language.set(normalize_language(selected))
                groq_key_status_var.set(_groq_key_status(new_config))
                if new_config.device == "cuda" and not gpu_available():
                    status_var.set(text_value("processing_gpu_unavailable"))
                elif save_changes:
                    status_var.set(f"{text_value('saved')} {text_value('processing_device_saved')}")
                else:
                    status_var.set(text_value("processing_device_saved"))
                render_settings()
            except Exception as exc:
                status_var.set(f"{text_value('settings_error')}: {exc}")

        def exit_app(root: tk.Tk) -> None:
            self._app.stop()
            self._close(root)

        def update_runtime_status() -> None:
            try:
                status = AppStatus(self._app.status_text)
                runtime_status_var.set(f"{text_value('status_prefix')}: {status_label(language(), status)}")
            except Exception:
                runtime_status_var.set(f"{text_value('status_prefix')}: {self._app.status_text}")
            sync_stats_variables()
            if self._root:
                root.after(300, update_runtime_status)

        sync_display_variables()
        render_main()
        update_runtime_status()
        root.mainloop()

    def _load_assets(self, root: tk.Tk) -> None:
        self._images = {}
        for key, relative in {
            "brand_mark": Path("ui") / "voicetype-mark-48.png",
            "app_icon_16": Path("brand") / "voicetype-16.png",
            "app_icon_20": Path("brand") / "voicetype-20.png",
            "app_icon_24": Path("brand") / "voicetype-24.png",
            "app_icon_32": Path("brand") / "voicetype-32.png",
            "app_icon_40": Path("brand") / "voicetype-40.png",
            "app_icon_48": Path("brand") / "voicetype-48.png",
            "app_icon_64": Path("brand") / "voicetype-64.png",
            "app_icon_128": Path("brand") / "voicetype-128.png",
            "app_icon_256": Path("brand") / "voicetype-256.png",
            "keyboard": Path("figma") / "keyboard.png",
            "recognition": Path("figma") / "recognition.png",
            "model": Path("figma") / "model.png",
            "chevron": Path("figma") / "chevron-down.png",
            "power": Path("figma") / "power.png",
        }.items():
            path = _asset_path(relative)
            if not path:
                continue
            try:
                self._images[key] = tk.PhotoImage(master=root, file=str(path))
            except tk.TclError:
                continue

    def _apply_window_icon(self, root: tk.Tk) -> None:
        icons = [
            self._images.get(f"app_icon_{size}")
            for size in (256, 128, 64, 48, 40, 32, 24, 20, 16)
        ]
        icons = [icon for icon in icons if icon]
        if icons:
            try:
                root.iconphoto(True, *icons)
            except tk.TclError:
                pass
        ico = _asset_path(Path("brand") / "voicetype.ico")
        if ico:
            try:
                root.iconbitmap(default=str(ico))
            except tk.TclError:
                pass

    def _hide(self, root: tk.Tk) -> None:
        if self._stop_microphone_test:
            self._stop_microphone_test()
        self._app.cancel_hotkey_capture()
        root.withdraw()

    def _close(self, root: tk.Tk) -> None:
        if self._stop_microphone_test:
            self._stop_microphone_test()
        self._app.cancel_hotkey_capture()
        root.destroy()
        self._root = None


class SmoothCanvas(tk.Canvas):
    def __init__(self, master, width: int, height: int, bg: str, cursor: str | None = None):
        options = {"width": width, "height": height, "bg": bg, "highlightthickness": 0, "bd": 0}
        if cursor:
            options["cursor"] = cursor
        super().__init__(master, **options)
        self._image_refs: list[ImageTk.PhotoImage] = []

    def _set_image(self, image: Image.Image) -> None:
        self.delete("all")
        photo = ImageTk.PhotoImage(image, master=self)
        self._image_refs = [photo]
        self.create_image(0, 0, image=photo, anchor="nw")

    def _redraw_safe(self) -> None:
        try:
            if self.winfo_exists():
                self._draw()
        except tk.TclError:
            pass


class Card(SmoothCanvas):
    def __init__(self, master, width: int, height: int, radius: int = 18):
        self.content_bg = COLORS["card"]
        super().__init__(master, width, height, COLORS["shell"])
        self._width = width
        self._height = height
        self._radius = radius
        self._draw()

    def _draw(self) -> None:
        image = _rounded_surface(
            self._width,
            self._height,
            self._radius,
            fill=COLORS["card"],
            outline=COLORS["border"],
            shadow=True,
            shadow_color=(68, 54, 34, 20),
            shadow_offset=(0, 4),
            shadow_blur=8,
        )
        self._set_image(image)


class BrandMark(tk.Frame):
    def __init__(self, master, image: tk.PhotoImage | None):
        super().__init__(master, width=48, height=48, bg=COLORS["header"])
        if image:
            tk.Label(self, image=image, bg=COLORS["header"], bd=0).place(x=0, y=0, width=48, height=48)
        else:
            badge = SmoothCanvas(self, 48, 48, COLORS["header"])
            badge.place(x=0, y=0)
            badge._set_image(_rounded_surface(48, 48, 13, COLORS["accent_soft"]))
            badge.create_text(24, 24, text="V", fill=COLORS["text"], font=("Arial", 18, "bold"))


class StatusPill(SmoothCanvas):
    def __init__(self, master, variable: tk.StringVar, font: tkfont.Font, width: int = 146):
        super().__init__(master, width, 34, COLORS["header"])
        self._width = width
        self._variable = variable
        self._font = font
        self._variable.trace_add("write", lambda *_: self._redraw_safe())
        self._draw()

    def _draw(self) -> None:
        self._set_image(
            _rounded_surface(
                self._width,
                34,
                17,
                fill=COLORS["pill"],
                outline="#e4ded5",
                shadow=False,
            )
        )
        dot = _circle_photo(8, fill=COLORS["gold_deep"], shadow=True, master=self)
        self._image_refs.append(dot)
        self.create_image(21, 17, image=dot)
        self.create_text(33, 17, text=self._variable.get(), anchor="w", fill="#5c513b", font=self._font, width=self._width - 42)


class IconLabel(tk.Frame):
    def __init__(
        self,
        master,
        text: str,
        font: tkfont.Font,
        image: tk.PhotoImage | None,
        icon_size: int,
        lines: int = 1,
    ):
        super().__init__(master, bg=COLORS["card"])
        icon = tk.Canvas(self, width=icon_size, height=icon_size, bg=COLORS["card"], highlightthickness=0, bd=0)
        icon.grid(row=0, column=0, sticky="n", pady=(2 if lines == 1 else 8, 0))
        if image:
            icon.create_image(icon_size // 2, icon_size // 2, image=image)
        else:
            dot = _circle_photo(icon_size, fill=COLORS["gold_deep"], master=icon)
            icon._image_ref = dot
            icon.create_image(icon_size // 2, icon_size // 2, image=dot)
        tk.Label(
            self,
            text=text,
            bg=COLORS["card"],
            fg=COLORS["text"],
            font=font,
            justify="left",
            anchor="w",
        ).grid(row=0, column=1, sticky="w", padx=(8, 0))


class HotkeyField(SmoothCanvas):
    def __init__(
        self,
        master,
        variable: tk.StringVar,
        font: tkfont.Font,
        image: tk.PhotoImage | None,
        width: int,
        height: int,
    ):
        super().__init__(master, width, height, COLORS["card"])
        self._variable = variable
        self._font = font
        self._image = image
        self._width = width
        self._height = height
        self._variable.trace_add("write", lambda *_: self._redraw_safe())
        self._draw()

    def _draw(self) -> None:
        self._set_image(
            _rounded_surface(
                self._width,
                self._height,
                12,
                fill=COLORS["field"],
                outline=COLORS["border_soft"],
                inner_highlight=True,
            )
        )
        self.create_text(18, self._height // 2, text=self._variable.get(), anchor="w", fill=COLORS["text"], font=self._font, width=self._width - 56)
        if self._image:
            self._image_refs.append(self._image)
            self.create_image(self._width - 20, self._height // 2, image=self._image)
        else:
            self.create_text(self._width - 20, self._height // 2, text="⌨", fill=COLORS["caption"], font=self._font)


class SelectBox(SmoothCanvas):
    _open_dropdown: "SelectBox | None" = None

    def __init__(
        self,
        master,
        variable: tk.StringVar,
        values: tuple[str, ...],
        font: tkfont.Font,
        image: tk.PhotoImage | None,
        width: int,
        height: int,
    ):
        super().__init__(master, width, height, COLORS["card"], cursor="hand2")
        self._variable = variable
        self._values = values
        self._font = font
        self._image = image
        self._width = width
        self._height = height
        self._hover = False
        self._dropdown: tk.Toplevel | None = None
        self._closed_at = 0.0
        self._variable.trace_add("write", lambda *_: self._redraw_safe())
        self.bind("<Button-1>", self._toggle_dropdown)
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self._draw()

    def _enter(self, _event=None) -> None:
        self._hover = True
        self._draw()

    def _leave(self, _event=None) -> None:
        self._hover = False
        self._draw()

    def _draw(self) -> None:
        self._set_image(
            _rounded_surface(
                self._width,
                self._height,
                12,
                fill=COLORS["field_hover"] if self._hover else COLORS["field"],
                outline=COLORS["border_soft"],
                inner_highlight=True,
            )
        )
        self.create_text(17, self._height // 2, text=self._variable.get(), anchor="w", fill=COLORS["text"], font=self._font, width=self._width - 56)
        if self._image:
            self._image_refs.append(self._image)
            self.create_image(self._width - 20, self._height // 2, image=self._image)
        else:
            self.create_text(self._width - 20, self._height // 2, text="⌄", fill=COLORS["muted"], font=self._font)

    def _toggle_dropdown(self, _event=None) -> None:
        if time.monotonic() - self._closed_at < 0.12:
            return
        if self._dropdown:
            self._close_dropdown()
            return
        if SelectBox._open_dropdown and SelectBox._open_dropdown is not self:
            SelectBox._open_dropdown._close_dropdown()
        SelectBox._open_dropdown = self
        row_h = 40
        width = self._width
        height = max(row_h + 10, row_h * len(self._values) + 12)
        dropdown = tk.Toplevel(self)
        self._dropdown = dropdown
        dropdown.overrideredirect(True)
        dropdown.configure(bg=COLORS["shell"])
        dropdown.geometry(f"{width}x{height}+{self.winfo_rootx()}+{self.winfo_rooty() + self._height + 6}")
        dropdown.attributes("-topmost", True)
        surface = SmoothCanvas(dropdown, width, height, COLORS["shell"])
        surface.place(x=0, y=0)
        surface._set_image(
            _rounded_surface(
                width,
                height,
                12,
                fill=COLORS["card"],
                outline=COLORS["border_soft"],
                shadow=True,
                shadow_blur=10,
                shadow_offset=(0, 4),
            )
        )
        for index, value in enumerate(self._values):
            OptionRow(surface, value, self._variable.get() == value, self._font, lambda selected=value: self._select(selected)).place(
                x=6,
                y=5 + index * row_h,
                width=width - 12,
                height=row_h - 1,
            )
        dropdown.bind("<Escape>", lambda _event: self._close_dropdown())
        dropdown.after(50, dropdown.focus_force)

    def _select(self, value: str) -> None:
        self._variable.set(value)
        self._close_dropdown()

    def _close_dropdown(self) -> None:
        if self._dropdown:
            self._dropdown.destroy()
            self._dropdown = None
            self._closed_at = time.monotonic()
        if SelectBox._open_dropdown is self:
            SelectBox._open_dropdown = None


class OptionRow(SmoothCanvas):
    def __init__(self, master, text: str, selected: bool, font: tkfont.Font, command):
        super().__init__(master, 1, 1, COLORS["card"], cursor="hand2")
        self._text = text
        self._selected = selected
        self._font = font
        self._command = command
        self._hover = False
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<Button-1>", self._click)
        self.bind("<Configure>", lambda _event: self._draw())

    def _click(self, _event=None):
        self._command()
        return "break"

    def _enter(self, _event=None) -> None:
        self._hover = True
        self._draw()

    def _leave(self, _event=None) -> None:
        self._hover = False
        self._draw()

    def _draw(self) -> None:
        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())
        self._set_image(
            _rounded_surface(
                width,
                height,
                9,
                fill=COLORS["field"] if self._hover or self._selected else COLORS["card"],
                outline="",
            )
        )
        self.create_text(12, height // 2, text=self._text, anchor="w", fill=COLORS["text"], font=self._font, width=width - 34)
        if self._selected:
            dot = _circle_photo(8, fill=COLORS["gold_deep"], master=self)
            self._image_refs.append(dot)
            self.create_image(width - 18, height // 2, image=dot)


class RadioOption(tk.Frame):
    def __init__(
        self,
        master,
        variable: tk.StringVar,
        value: str,
        title: str,
        subtitle: str,
        fonts: dict[str, tkfont.Font],
    ):
        super().__init__(master, width=289, height=38, bg=COLORS["card"], cursor="hand2")
        self._variable = variable
        self._value = value
        self._circle = SmoothCanvas(self, 22, 22, COLORS["card"], cursor="hand2")
        self._circle.place(x=0, y=3)
        tk.Label(self, text=title, bg=COLORS["card"], fg=COLORS["text"], font=fonts["button"], cursor="hand2").place(x=32, y=0)
        tk.Label(self, text=subtitle, bg=COLORS["card"], fg=COLORS["caption"], font=fonts["caption"], cursor="hand2").place(x=32, y=21)
        self._variable.trace_add("write", lambda *_: self._redraw_safe())
        _bind_click_tree(self, self._select)
        self._draw()

    def _select(self, _event=None) -> None:
        self._variable.set(self._value)

    def _redraw_safe(self) -> None:
        try:
            if self.winfo_exists():
                self._draw()
        except tk.TclError:
            pass

    def _draw(self) -> None:
        selected = self._variable.get() == self._value
        self._circle._set_image(_radio_image(selected))


class ToggleSwitch(SmoothCanvas):
    def __init__(self, master, variable: tk.BooleanVar):
        super().__init__(master, 52, 28, COLORS["card"], cursor="hand2")
        self._variable = variable
        self._variable.trace_add("write", lambda *_: self._redraw_safe())
        self.bind("<Button-1>", self._toggle)
        self._draw()

    def _toggle(self, _event=None) -> None:
        self._variable.set(not bool(self._variable.get()))

    def _draw(self) -> None:
        self._set_image(_toggle_image(bool(self._variable.get())))


class LevelMeter(SmoothCanvas):
    def __init__(self, master, variable: tk.DoubleVar, width: int, height: int):
        super().__init__(master, width, height, COLORS["card"])
        self._variable = variable
        self._width = width
        self._height = height
        self._variable.trace_add("write", lambda *_: self._redraw_safe())
        self._draw()

    def _draw(self) -> None:
        value = max(0.0, min(1.0, float(self._variable.get())))
        image = _level_meter_image(self._width, self._height, value)
        self._set_image(image)


class RoundedButton(SmoothCanvas):
    def __init__(
        self,
        master,
        text: str,
        command,
        font: tkfont.Font,
        width: int,
        height: int,
        fill: str,
        hover_fill: str,
        fg: str,
        border: str = "",
        radius: int = 11,
        shadow: bool = False,
        active_fill: str | None = None,
        active_var: tk.BooleanVar | None = None,
    ):
        self.content_bg = getattr(master, "content_bg", None) or _bg(master)
        super().__init__(master, width, height, self.content_bg, cursor="hand2")
        self._text = text
        self._command = command
        self._font = font
        self._width = width
        self._height = height
        self._fill = fill
        self._hover_fill = hover_fill
        self._fg = fg
        self._border = border
        self._radius = radius
        self._shadow = shadow
        self._active_fill = active_fill
        self._active_var = active_var
        self._hover = False
        if self._active_var is not None:
            self._active_var.trace_add("write", lambda *_: self._redraw_safe())
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<ButtonRelease-1>", self._click)
        self._draw()

    def _enter(self, _event=None) -> None:
        self._hover = True
        self._draw()

    def _leave(self, _event=None) -> None:
        self._hover = False
        self._draw()

    def _click(self, _event=None) -> None:
        if self._command:
            self._command()

    def _draw(self) -> None:
        active = bool(self._active_var.get()) if self._active_var is not None else False
        fill = self._active_fill if active and self._active_fill else self._hover_fill if self._hover else self._fill
        self._set_image(
            _rounded_surface(
                self._width,
                self._height,
                self._radius,
                fill=fill,
                outline=self._border,
                shadow=self._shadow or active,
                shadow_blur=8 if active else 6,
                shadow_offset=(0, 3 if active else 2),
                shadow_color=(104, 79, 39, 48) if active else (0, 0, 0, 42),
                inner_highlight=self._fill != COLORS["black"],
            )
        )
        self.create_text(self._width // 2, self._height // 2, text=self._text, fill=self._fg, font=self._font)


class TextButton(tk.Label):
    def __init__(self, master, text: str, command, font: tkfont.Font):
        super().__init__(master, text=text, bg=COLORS["footer"], fg=COLORS["muted"], font=font, cursor="hand2", padx=16, pady=8)
        self._command = command
        self.bind("<ButtonRelease-1>", lambda _event: self._command())
        self.bind("<Enter>", lambda _event: self.configure(fg=COLORS["text"]))
        self.bind("<Leave>", lambda _event: self.configure(fg=COLORS["muted"]))


class WindowButton(SmoothCanvas):
    def __init__(self, master, text: str, tooltip: str, command, font: tkfont.Font):
        super().__init__(master, 32, 32, COLORS["header"], cursor="hand2")
        self._text = text
        self._tooltip = tooltip
        self._command = command
        self._font = font
        self._hover = False
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<ButtonRelease-1>", self._click)
        self._draw()

    def _enter(self, _event=None) -> None:
        self._hover = True
        self._draw()

    def _leave(self, _event=None) -> None:
        self._hover = False
        self._draw()

    def _click(self, _event=None) -> None:
        if self._command:
            self._command()

    def _draw(self) -> None:
        fill = COLORS["field"] if self._hover else COLORS["header"]
        outline = COLORS["border"] if self._hover else ""
        self._set_image(_rounded_surface(32, 32, 10, fill=fill, outline=outline, inner_highlight=self._hover))
        self.create_text(16, 15, text=self._text, fill=COLORS["muted"], font=self._font)


def _build_model_card(
    card: Card,
    title: str,
    variable: tk.StringVar,
    values: tuple[str, ...],
    status_var: tk.StringVar | None,
    fonts: dict[str, tkfont.Font],
    images: dict[str, tk.PhotoImage],
) -> None:
    IconLabel(card, title, fonts["section"], images.get("model"), icon_size=18).place(x=25, y=25)
    SelectBox(card, variable, values, fonts["body"], images.get("chevron"), width=289, height=54).place(x=25, y=69)
    if status_var is not None:
        tk.Label(card, textvariable=status_var, bg=COLORS["card"], fg=COLORS["caption"], font=fonts["caption"], anchor="w").place(
            x=25,
            y=126,
            width=289,
            height=18,
        )


def _place_stat(
    master: tk.Widget,
    label: str,
    value_var: tk.StringVar,
    fonts: dict[str, tkfont.Font],
    x: int,
    y: int,
) -> None:
    tk.Label(
        master,
        textvariable=value_var,
        bg=COLORS["card"],
        fg=COLORS["text"],
        font=fonts["metric"],
        anchor="w",
    ).place(x=x, y=y, width=130, height=34)
    tk.Label(
        master,
        text=label,
        bg=COLORS["card"],
        fg=COLORS["caption"],
        font=fonts["caption"],
        anchor="w",
        wraplength=130,
    ).place(x=x, y=y + 39, width=138, height=32)


def _rounded_surface(
    width: int,
    height: int,
    radius: int,
    fill: str,
    outline: str = "",
    shadow: bool = False,
    shadow_color: tuple[int, int, int, int] = (0, 0, 0, 28),
    shadow_offset: tuple[int, int] = (0, 3),
    shadow_blur: int = 7,
    inner_highlight: bool = False,
) -> Image.Image:
    scale = AA_SCALE
    w, h = width * scale, height * scale
    r = radius * scale
    image = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    box = [2 * scale, 2 * scale, w - 2 * scale - 1, h - 3 * scale - 1]
    if shadow:
        shadow_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow_layer)
        sx, sy = shadow_offset[0] * scale, shadow_offset[1] * scale
        sd.rounded_rectangle([box[0] + sx, box[1] + sy, box[2] + sx, box[3] + sy], radius=r, fill=shadow_color)
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(shadow_blur * scale))
        image.alpha_composite(shadow_layer)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(box, radius=r, fill=fill, outline=outline if outline else None, width=max(1, scale))
    if inner_highlight:
        draw.rounded_rectangle(
            [box[0] + scale, box[1] + scale, box[2] - scale, box[3] - scale],
            radius=max(1, r - scale),
            outline=(255, 255, 255, 120),
            width=max(1, scale // 2),
        )
    return image.resize((width, height), Image.Resampling.LANCZOS)


def _circle_photo(size: int, fill: str, master: tk.Widget, shadow: bool = False) -> ImageTk.PhotoImage:
    scale = AA_SCALE
    pad = 4 if shadow else 1
    canvas = Image.new("RGBA", ((size + pad * 2) * scale, (size + pad * 2) * scale), (0, 0, 0, 0))
    if shadow:
        sd = ImageDraw.Draw(canvas)
        sd.ellipse(
            [(pad + 1) * scale, (pad + 2) * scale, (pad + size + 1) * scale, (pad + size + 2) * scale],
            fill=(0, 0, 0, 52),
        )
        canvas = canvas.filter(ImageFilter.GaussianBlur(2 * scale))
    draw = ImageDraw.Draw(canvas)
    draw.ellipse([pad * scale, pad * scale, (pad + size) * scale, (pad + size) * scale], fill=fill)
    image = canvas.resize((size + pad * 2, size + pad * 2), Image.Resampling.LANCZOS)
    return ImageTk.PhotoImage(image, master=master)


def _radio_image(selected: bool) -> Image.Image:
    scale = AA_SCALE
    width = height = 22
    img = Image.new("RGBA", (width * scale, height * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    if selected:
        draw.ellipse([1 * scale, 1 * scale, 21 * scale, 21 * scale], fill=COLORS["gold_deep"])
        draw.ellipse([6 * scale, 6 * scale, 16 * scale, 16 * scale], fill=COLORS["accent_soft"])
        draw.ellipse([9 * scale, 9 * scale, 13 * scale, 13 * scale], fill=COLORS["graphite"])
    else:
        draw.ellipse([2 * scale, 2 * scale, 20 * scale, 20 * scale], fill=COLORS["card"], outline="#cfc5b8", width=2 * scale)
    return img.resize((width, height), Image.Resampling.LANCZOS)


def _toggle_image(enabled: bool) -> Image.Image:
    scale = AA_SCALE
    width, height = 52, 28
    img = Image.new("RGBA", (width * scale, height * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    track = "#cdb88f" if enabled else "#e7e0d7"
    outline = "#bea77c" if enabled else "#d4cabe"
    draw.rounded_rectangle([1 * scale, 2 * scale, 51 * scale, 26 * scale], radius=13 * scale, fill=track, outline=outline, width=scale)
    draw.rounded_rectangle([3 * scale, 4 * scale, 49 * scale, 24 * scale], radius=11 * scale, outline=(255, 255, 255, 98), width=scale)
    knob_x = 27 if enabled else 3
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse([knob_x * scale, 4 * scale, (knob_x + 22) * scale, 26 * scale], fill=(0, 0, 0, 44))
    shadow = shadow.filter(ImageFilter.GaussianBlur(2 * scale))
    img.alpha_composite(shadow)
    draw = ImageDraw.Draw(img)
    draw.ellipse([knob_x * scale, 3 * scale, (knob_x + 22) * scale, 25 * scale], fill="#fffdf9", outline="#ffffff", width=scale)
    draw.ellipse([(knob_x + 4) * scale, 7 * scale, (knob_x + 18) * scale, 21 * scale], outline=(255, 255, 255, 80), width=scale)
    return img.resize((width, height), Image.Resampling.LANCZOS)


def _level_meter_image(width: int, height: int, value: float) -> Image.Image:
    scale = AA_SCALE
    w, h = width * scale, height * scale
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    radius = (height // 2) * scale
    box = [1 * scale, 2 * scale, w - 1 * scale, h - 2 * scale]
    draw.rounded_rectangle(box, radius=radius, fill=COLORS["field"], outline=COLORS["border_soft"], width=scale)
    draw.rounded_rectangle(
        [box[0] + scale, box[1] + scale, box[2] - scale, box[3] - scale],
        radius=max(1, radius - scale),
        outline=(255, 255, 255, 120),
        width=scale,
    )
    fill_width = int((width - 4) * max(0.0, min(1.0, value))) * scale
    if fill_width > 2 * scale:
        fill_box = [2 * scale, 3 * scale, 2 * scale + fill_width, h - 3 * scale]
        fill = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        fd = ImageDraw.Draw(fill)
        fd.rounded_rectangle(fill_box, radius=max(1, radius - scale), fill=COLORS["accent_soft"])
        glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gd.rounded_rectangle(fill_box, radius=max(1, radius - scale), fill=(212, 189, 146, 56))
        glow = glow.filter(ImageFilter.GaussianBlur(4 * scale))
        img.alpha_composite(glow)
        img.alpha_composite(fill)
    return img.resize((width, height), Image.Resampling.LANCZOS)


def _configure_borderless(root: tk.Tk) -> None:
    root.overrideredirect(True)
    root.bind("<Map>", lambda event: root.after(20, lambda: _restore_borderless(root)) if event.widget is root else None)
    root.after(80, lambda: _enable_taskbar_icon(root, refresh=True))


def _restore_borderless(root: tk.Tk) -> None:
    if not root.winfo_exists() or root.state() != "normal":
        return
    root.overrideredirect(True)
    _enable_taskbar_icon(root)


def _minimize_window(root: tk.Tk) -> None:
    root.update_idletasks()
    root.overrideredirect(False)
    root.iconify()


def _enable_taskbar_icon(root: tk.Tk, refresh: bool = False) -> None:
    if sys.platform != "win32" or not root.winfo_exists():
        return
    try:
        root.update_idletasks()
        user32 = ctypes.windll.user32
        hwnds = {int(root.winfo_id())}
        parent = int(user32.GetParent(root.winfo_id()))
        if parent:
            hwnds.add(parent)

        get_long = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
        set_long = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
        for hwnd in hwnds:
            ex_style = int(get_long(hwnd, -20))
            ex_style = (ex_style | 0x00040000) & ~0x00000080
            set_long(hwnd, -20, ex_style)

        if refresh and root.state() != "withdrawn" and not getattr(root, "_taskbar_refreshing", False):
            root._taskbar_refreshing = True
            root.withdraw()

            def show_again() -> None:
                if root.winfo_exists():
                    root.deiconify()
                    root.lift()
                    root._taskbar_refreshing = False

            root.after(25, show_again)
    except Exception:
        pass


def _bind_drag_tree(widget: tk.Widget, root: tk.Tk, skip_types: tuple[type, ...] = ()) -> None:
    if isinstance(widget, skip_types):
        return

    def start(event) -> None:
        root._drag_offset = (event.x_root - root.winfo_x(), event.y_root - root.winfo_y())

    def move(event) -> None:
        offset_x, offset_y = getattr(root, "_drag_offset", (0, 0))
        root.geometry(f"+{event.x_root - offset_x}+{event.y_root - offset_y}")

    widget.bind("<Button-1>", start, add="+")
    widget.bind("<B1-Motion>", move, add="+")
    for child in widget.winfo_children():
        _bind_drag_tree(child, root, skip_types=skip_types)


def _make_scroll_area(master: tk.Widget, width: int, height: int, content_height: int) -> tk.Frame:
    canvas = tk.Canvas(
        master,
        width=width,
        height=height,
        bg=COLORS["shell"],
        highlightthickness=0,
        borderwidth=0,
        yscrollincrement=18,
    )
    canvas.place(x=0, y=0)
    body = tk.Frame(canvas, width=width, height=content_height, bg=COLORS["shell"])
    body.place(x=0, y=0)
    canvas.create_window(0, 0, window=body, anchor="nw", width=width, height=content_height)
    canvas.configure(scrollregion=(0, 0, width, content_height))

    def on_wheel(event) -> str:
        delta = -1 if event.delta > 0 else 1
        canvas.yview_scroll(delta * 3, "units")
        return "break"

    _bind_mousewheel_tree(body, on_wheel)
    canvas.bind("<MouseWheel>", on_wheel, add="+")
    body._refresh_mousewheel_bindings = lambda: _bind_mousewheel_tree(body, on_wheel)
    return body


def _bind_mousewheel_tree(widget: tk.Widget, callback) -> None:
    widget.bind("<MouseWheel>", callback, add="+")
    for child in widget.winfo_children():
        _bind_mousewheel_tree(child, callback)


def _load_private_font(relative: Path) -> None:
    if sys.platform != "win32":
        return
    path = _asset_path(relative)
    if not path:
        return
    try:
        ctypes.windll.gdi32.AddFontResourceExW(str(path), 0x10, 0)
    except Exception:
        pass


def _make_fonts(root: tk.Tk) -> dict[str, tkfont.Font]:
    families = set(tkfont.families(root))
    title_family = "Archivo Black" if "Archivo Black" in families else "Bahnschrift"
    if title_family not in families:
        title_family = "Segoe UI Variable Display" if "Segoe UI Variable Display" in families else "Segoe UI"
    ui_family = "Manrope" if "Manrope" in families else "Segoe UI Variable Display" if "Segoe UI Variable Display" in families else "Segoe UI"
    return {
        "title": tkfont.Font(root=root, family=title_family, size=-24, weight="normal"),
        "section": tkfont.Font(root=root, family=ui_family, size=-19, weight="bold"),
        "body": tkfont.Font(root=root, family=ui_family, size=-13, weight="bold"),
        "body_bold": tkfont.Font(root=root, family=ui_family, size=-13, weight="bold"),
        "button": tkfont.Font(root=root, family=ui_family, size=-13, weight="bold"),
        "metric": tkfont.Font(root=root, family=ui_family, size=-28, weight="bold"),
        "caption": tkfont.Font(root=root, family=ui_family, size=-11, weight="bold"),
        "caption_bold": tkfont.Font(root=root, family=ui_family, size=-11, weight="bold"),
        "status": tkfont.Font(root=root, family=ui_family, size=-11, weight="bold"),
        "window": tkfont.Font(root=root, family=ui_family, size=-16, weight="bold"),
    }


def _bind_click_tree(widget: tk.Widget, callback) -> None:
    widget.bind("<Button-1>", callback)
    for child in widget.winfo_children():
        _bind_click_tree(child, callback)


def _bg(widget: tk.Widget) -> str:
    try:
        return str(widget.cget("bg"))
    except tk.TclError:
        return COLORS["shell"]


def _asset_path(relative: Path) -> Path | None:
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).parent / "assets" / relative)
        bundle_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        candidates.append(bundle_dir / "assets" / relative)
    candidates.extend(
        [
            Path(__file__).resolve().parents[2] / "assets" / relative,
            Path.cwd() / "assets" / relative,
        ]
    )
    for path in candidates:
        if path.exists():
            return path
    return None


def _groq_key_status(config: AppConfig) -> str:
    if os.environ.get(config.groq_api_key_env):
        return f"{config.groq_api_key_env}: найден"
    return f"{config.groq_api_key_env}: не задан"


def _autostart_state(config: AppConfig) -> bool:
    return bool(config.autostart)


def _format_int(value: int) -> str:
    return f"{int(value):,}".replace(",", " ")


def _format_number(value: float) -> str:
    if value <= 0:
        return "0"
    if value >= 10:
        return f"{value:.0f}"
    return f"{value:.1f}"


def _label_for(labels: dict[str, str], value: str) -> str:
    return labels.get(value, value)


def _value_for_any(label_groups: tuple[dict[str, str], ...], display: str, default: str) -> str:
    display = display.strip()
    for labels in label_groups:
        if display in labels:
            return display
        for value, label in labels.items():
            if display == label:
                return value
    return default
