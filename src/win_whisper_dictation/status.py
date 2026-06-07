from enum import Enum


class AppStatus(str, Enum):
    IDLE = "idle"
    PAUSED = "paused"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    PASTING = "pasting"
    PASTED = "pasted"
    ERROR = "error"


STATUS_LABELS = {
    AppStatus.IDLE: "Готово",
    AppStatus.PAUSED: "Пауза",
    AppStatus.RECORDING: "Запись",
    AppStatus.TRANSCRIBING: "Распознавание",
    AppStatus.PASTING: "Вставка",
    AppStatus.PASTED: "Вставлено",
    AppStatus.ERROR: "Ошибка",
}
