from __future__ import annotations

import os
import threading
import tkinter as tk
from dataclasses import replace
from tkinter import messagebox, ttk

from .config import AppConfig
from .hotkey_spec import parse_hotkey
from .status import STATUS_LABELS, AppStatus


APP_NAME = "VoiceType"

PROVIDER_LABELS = {
    "groq": "Нейросеть Groq",
    "local": "Локально (медленнее, без интернета)",
}

GROQ_MODEL_LABELS = {
    "whisper-large-v3-turbo": "Быстрая нейросеть (рекомендуется)",
    "whisper-large-v3": "Точная нейросеть",
}

LOCAL_MODEL_LABELS = {
    "tiny": "Самая быстрая (ниже точность)",
    "base": "Быстрая",
    "small": "Сбалансированная",
    "medium": "Точная (медленнее)",
    "large-v3": "Максимальная точность",
    "distil-large-v3": "Быстрая большая модель",
}


class SettingsWindow:
    def __init__(self, app):
        self._app = app
        self._thread: threading.Thread | None = None
        self._root: tk.Tk | None = None

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

    def _run(self) -> None:
        config = self._app.config
        root = tk.Tk()
        self._root = root
        root.title(APP_NAME)
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", lambda: self._hide(root))

        hotkey_var = tk.StringVar(value=parse_hotkey(config.hotkey).display)
        hotkey_canonical = tk.StringVar(value=config.hotkey)
        status_var = tk.StringVar(value="")
        runtime_status_var = tk.StringVar(value="Статус: Готово")
        provider_var = tk.StringVar(value=_label_for(PROVIDER_LABELS, config.provider))
        groq_model_var = tk.StringVar(value=_label_for(GROQ_MODEL_LABELS, config.groq_model))
        groq_key_status_var = tk.StringVar(value=_groq_key_status(config))
        model_var = tk.StringVar(value=_label_for(LOCAL_MODEL_LABELS, config.model))
        autostart_var = tk.BooleanVar(value=config.autostart)

        frame = ttk.Frame(root, padding=14)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(1, weight=1)

        title = ttk.Label(frame, text=f"{APP_NAME} запущен", font=("Segoe UI", 10, "bold"))
        title.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))
        help_text = ttk.Label(
            frame,
            text="Откройте любое поле ввода, удерживайте горячую клавишу, говорите и отпустите её.",
            foreground="#555555",
        )
        help_text.grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 12))

        status_label = ttk.Label(frame, textvariable=runtime_status_var, foreground="#1f4f8f")
        status_label.grid(row=2, column=0, columnspan=3, sticky="w", pady=(0, 10))

        ttk.Label(frame, text="Горячая клавиша").grid(row=3, column=0, sticky="w", pady=(0, 6))
        hotkey_entry = ttk.Entry(frame, textvariable=hotkey_var, state="readonly", width=28)
        hotkey_entry.grid(row=3, column=1, sticky="ew", pady=(0, 6))
        ttk.Button(frame, text="Назначить", command=lambda: record_hotkey()).grid(
            row=3, column=2, padx=(8, 0), pady=(0, 6)
        )

        ttk.Label(frame, text="Распознавание").grid(row=4, column=0, sticky="w", pady=6)
        ttk.Combobox(
            frame,
            textvariable=provider_var,
            values=tuple(PROVIDER_LABELS.values()),
            state="readonly",
            width=25,
        ).grid(row=4, column=1, columnspan=2, sticky="ew", pady=6)

        groq_model_label = ttk.Label(frame, text="Модель нейросети")
        groq_model_label.grid(row=5, column=0, sticky="w", pady=6)
        groq_model_combo = ttk.Combobox(
            frame,
            textvariable=groq_model_var,
            values=tuple(GROQ_MODEL_LABELS.values()),
            state="readonly",
            width=25,
        )
        groq_model_combo.grid(row=5, column=1, columnspan=2, sticky="ew", pady=6)

        groq_key_label = ttk.Label(frame, textvariable=groq_key_status_var, foreground="#666666")
        groq_key_label.grid(row=6, column=1, columnspan=2, sticky="w", pady=(0, 6))

        local_model_label = ttk.Label(frame, text="Локальная модель")
        local_model_label.grid(row=7, column=0, sticky="w", pady=6)
        local_model_combo = ttk.Combobox(
            frame,
            textvariable=model_var,
            values=tuple(LOCAL_MODEL_LABELS.values()),
            state="readonly",
            width=25,
        )
        local_model_combo.grid(row=7, column=1, columnspan=2, sticky="ew", pady=6)

        ttk.Checkbutton(frame, text="Запускать вместе с Windows", variable=autostart_var).grid(
            row=8, column=1, columnspan=2, sticky="w", pady=4
        )

        ttk.Label(frame, textvariable=status_var, foreground="#555555").grid(
            row=9, column=0, columnspan=3, sticky="w", pady=(8, 4)
        )

        buttons = ttk.Frame(frame)
        buttons.grid(row=10, column=0, columnspan=3, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="Выйти", command=lambda: exit_app(root)).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(buttons, text="Скрыть", command=lambda: self._hide(root)).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(buttons, text="Сохранить", command=lambda: save()).grid(row=0, column=2)

        def update_model_fields(*_args) -> None:
            provider = _value_for(PROVIDER_LABELS, provider_var.get(), "local")
            if provider == "groq":
                groq_model_label.grid()
                groq_model_combo.grid()
                groq_key_label.grid()
                local_model_label.grid_remove()
                local_model_combo.grid_remove()
            else:
                groq_model_label.grid_remove()
                groq_model_combo.grid_remove()
                groq_key_label.grid_remove()
                local_model_label.grid()
                local_model_combo.grid()

        provider_var.trace_add("write", update_model_fields)
        update_model_fields()

        def record_hotkey() -> None:
            status_var.set("Нажмите и отпустите нужную горячую клавишу...")

            def update(display: str) -> None:
                root.after(0, lambda: hotkey_var.set(display))

            def complete(canonical: str, display: str) -> None:
                def apply() -> None:
                    hotkey_canonical.set(canonical)
                    hotkey_var.set(display)
                    status_var.set("Горячая клавиша записана. Нажмите «Сохранить», чтобы применить.")

                root.after(0, apply)

            def error(message: str) -> None:
                root.after(0, lambda: status_var.set(message))

            self._app.begin_hotkey_capture(update, complete, error)

        def save() -> None:
            try:
                new_config = replace(
                    self._app.config,
                    hotkey=hotkey_canonical.get(),
                    provider=_value_for(PROVIDER_LABELS, provider_var.get(), "local"),
                    groq_model=_value_for(GROQ_MODEL_LABELS, groq_model_var.get(), "whisper-large-v3-turbo"),
                    model=_value_for(LOCAL_MODEL_LABELS, model_var.get(), "tiny"),
                    autostart=bool(autostart_var.get()),
                )
                self._app.apply_settings(new_config)
                groq_key_status_var.set(_groq_key_status(new_config))
                status_var.set("Сохранено.")
            except Exception as exc:
                messagebox.showerror("Ошибка настроек", str(exc), parent=root)

        def exit_app(root: tk.Tk) -> None:
            self._app.stop()
            self._close(root)

        def update_runtime_status() -> None:
            try:
                status = AppStatus(self._app.status_text)
                runtime_status_var.set(f"Статус: {STATUS_LABELS.get(status, status.value)}")
            except Exception:
                runtime_status_var.set(f"Статус: {self._app.status_text}")
            if self._root:
                root.after(300, update_runtime_status)

        update_runtime_status()

        root.mainloop()

    def _hide(self, root: tk.Tk) -> None:
        self._app.cancel_hotkey_capture()
        root.withdraw()

    def _close(self, root: tk.Tk) -> None:
        self._app.cancel_hotkey_capture()
        root.destroy()
        self._root = None


def _groq_key_status(config: AppConfig) -> str:
    if os.environ.get(config.groq_api_key_env):
        return f"{config.groq_api_key_env}: найден"
    return f"{config.groq_api_key_env}: не задан"


def _label_for(labels: dict[str, str], value: str) -> str:
    return labels.get(value, value)


def _value_for(labels: dict[str, str], display: str, default: str) -> str:
    display = display.strip()
    for value, label in labels.items():
        if display == label or display == value:
            return value
    return default
