from __future__ import annotations

from .status import AppStatus


SUPPORTED_LANGUAGES = ("ru", "en")
LOCAL_MODEL_VALUES = ("tiny", "small", "large-v3")
LEGACY_LOCAL_MODEL_MAP = {
    "tiny": "tiny",
    "base": "tiny",
    "small": "small",
    "medium": "large-v3",
    "large-v3": "large-v3",
    "distil-large-v3": "small",
}

TRANSLATIONS = {
    "ru": {
        "app_started": "Приложение запущено. Удерживайте {hotkey} для диктовки.",
        "already_running": "Приложение уже запущено.",
        "apply": "Применить",
        "autostart": "Автозапуск",
        "back": "Назад",
        "change": "Назначить",
        "close": "Закрыть",
        "exit": "Выйти",
        "groq_model": "Модель нейросети",
        "hide": "Скрыть",
        "hotkey": "Горячая клавиша",
        "hotkey_applied": "Горячая клавиша применена: {hotkey}.",
        "hotkey_error": "Ошибка горячей клавиши",
        "hotkey_subtitle": "Клавиша для активации записи голоса",
        "interface_language": "Язык интерфейса",
        "interface_language_subtitle": "Меняет язык элементов VoiceType",
        "language_en": "Английский",
        "language_ru": "Русский",
        "launch_with_windows": "Запускать вместе с\nWindows",
        "local_model": "Локальная модель",
        "minimize": "Свернуть",
        "pause": "Пауза",
        "press_hotkey": "Нажмите и отпустите нужную горячую клавишу...",
        "provider_groq": "Нейросеть Groq",
        "provider_groq_subtitle": "Быстрое облачное распознавание",
        "provider_local": "Локально",
        "provider_local_subtitle": "Медленнее, без интернета",
        "recognition": "Распознавание",
        "reload_settings": "Перезагрузить настройки",
        "resume": "Продолжить диктовку",
        "save": "Сохранить",
        "saved": "Сохранено.",
        "settings": "Настройки",
        "settings_error": "Ошибка настроек",
        "settings_hint": "Системные параметры интерфейса",
        "status_error": "Ошибка",
        "status_idle": "Готово",
        "status_pasting": "Вставка",
        "status_pasted": "Вставлено",
        "status_paused": "Пауза",
        "status_prefix": "Статус",
        "status_recording": "Идёт запись...",
        "status_transcribing": "Распознавание...",
        "tagline": "Не печатай, просто говори",
        "window_start_error": "Не удалось запустить приложение. Лог:\n{log}",
    },
    "en": {
        "app_started": "App started. Hold {hotkey} to dictate.",
        "already_running": "The app is already running.",
        "apply": "Apply",
        "autostart": "Autostart",
        "back": "Back",
        "change": "Change",
        "close": "Close",
        "exit": "Exit",
        "groq_model": "Neural Model",
        "hide": "Hide",
        "hotkey": "Hotkey",
        "hotkey_applied": "Hotkey applied: {hotkey}.",
        "hotkey_error": "Hotkey error",
        "hotkey_subtitle": "Key used to start voice recording",
        "interface_language": "Interface language",
        "interface_language_subtitle": "Changes VoiceType UI language",
        "language_en": "English",
        "language_ru": "Russian",
        "launch_with_windows": "Launch with\nWindows",
        "local_model": "Local Model",
        "minimize": "Minimize",
        "pause": "Pause",
        "press_hotkey": "Press and release the hotkey...",
        "provider_groq": "Groq Neural Network",
        "provider_groq_subtitle": "Fast cloud recognition",
        "provider_local": "Local",
        "provider_local_subtitle": "Slower, no internet",
        "recognition": "Recognition",
        "reload_settings": "Reload settings",
        "resume": "Resume dictation",
        "save": "Save",
        "saved": "Saved.",
        "settings": "Settings",
        "settings_error": "Settings error",
        "settings_hint": "System interface preferences",
        "status_error": "Error",
        "status_idle": "Ready",
        "status_pasting": "Pasting",
        "status_pasted": "Pasted",
        "status_paused": "Paused",
        "status_prefix": "Status",
        "status_recording": "Listening...",
        "status_transcribing": "Recognizing...",
        "tagline": "Don't type, just speak",
        "window_start_error": "Could not start the app. Log:\n{log}",
    },
}

GROQ_MODEL_LABELS = {
    "ru": {
        "whisper-large-v3-turbo": "Быстрая нейросеть (рекомендуется)",
        "whisper-large-v3": "Точная нейросеть",
    },
    "en": {
        "whisper-large-v3-turbo": "Fast Neural Model (recommended)",
        "whisper-large-v3": "Accurate Neural Model",
    },
}

LOCAL_MODEL_LABELS = {
    "ru": {
        "tiny": "Самая быстрая",
        "small": "Сбалансированная (медленнее)",
        "large-v3": "Максимальная точность (самая медленная)",
    },
    "en": {
        "tiny": "Fastest",
        "small": "Balanced (slower)",
        "large-v3": "Maximum accuracy (slowest)",
    },
}


def normalize_language(language: str) -> str:
    value = (language or "").strip().lower()
    return value if value in SUPPORTED_LANGUAGES else "ru"


def normalize_local_model(model: str) -> str:
    return LEGACY_LOCAL_MODEL_MAP.get((model or "").strip(), "tiny")


def t(language: str, key: str, **kwargs) -> str:
    lang = normalize_language(language)
    template = TRANSLATIONS[lang].get(key) or TRANSLATIONS["ru"].get(key) or key
    return template.format(**kwargs) if kwargs else template


def language_labels(language: str) -> dict[str, str]:
    lang = normalize_language(language)
    return {
        "ru": t(lang, "language_ru"),
        "en": t(lang, "language_en"),
    }


def provider_labels(language: str) -> dict[str, str]:
    lang = normalize_language(language)
    return {
        "groq": t(lang, "provider_groq"),
        "local": t(lang, "provider_local"),
    }


def groq_model_labels(language: str) -> dict[str, str]:
    return GROQ_MODEL_LABELS[normalize_language(language)]


def local_model_labels(language: str) -> dict[str, str]:
    return LOCAL_MODEL_LABELS[normalize_language(language)]


def status_label(language: str, status: AppStatus) -> str:
    return t(language, f"status_{status.value}")
