from __future__ import annotations

from collections.abc import Callable

import pystray
from PIL import Image, ImageDraw

from .status import AppStatus, STATUS_LABELS


APP_NAME = "VoiceType"

STATUS_COLORS = {
    AppStatus.IDLE: "#1f8f4d",
    AppStatus.PAUSED: "#777777",
    AppStatus.RECORDING: "#d93a34",
    AppStatus.TRANSCRIBING: "#3867d6",
    AppStatus.PASTING: "#b7791f",
    AppStatus.PASTED: "#1f8f4d",
    AppStatus.ERROR: "#b00020",
}


class TrayController:
    def __init__(self, app):
        self._app = app
        self._icon: pystray.Icon | None = None

    def run(self) -> None:
        self._icon = pystray.Icon(
            "VoiceType",
            _make_icon(AppStatus.IDLE),
            APP_NAME,
            self._menu(),
        )
        self._icon.run(setup=lambda icon: self._app.on_tray_ready())

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()

    def update_status(self, status: AppStatus, detail: str = "") -> None:
        if not self._icon:
            return
        label = STATUS_LABELS.get(status, status.value)
        self._icon.title = f"{APP_NAME} - {label}"
        self._icon.icon = _make_icon(status)
        try:
            self._icon.update_menu()
        except Exception:
            pass

    def notify(self, message: str) -> None:
        if not self._icon:
            return
        try:
            self._icon.notify(message, APP_NAME)
        except Exception:
            pass

    def _menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(self._pause_label, self._toggle_pause),
            pystray.MenuItem("Настройки", lambda _icon, _item: self._app.open_settings()),
            pystray.MenuItem("Перезагрузить настройки", lambda _icon, _item: self._app.reload_settings()),
            pystray.MenuItem(
                "Автозапуск",
                lambda _icon, _item: self._app.toggle_autostart(),
                checked=lambda _item: self._app.config.autostart,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Выход", lambda _icon, _item: self._app.stop()),
        )

    def _pause_label(self, _item) -> str:
        return "Продолжить диктовку" if self._app.paused else "Пауза"

    def _toggle_pause(self, _icon, _item) -> None:
        self._app.toggle_pause()


def _make_icon(status: AppStatus) -> Image.Image:
    color = STATUS_COLORS.get(status, STATUS_COLORS[AppStatus.IDLE])
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((6, 6, 58, 58), fill=color)
    draw.rounded_rectangle((25, 14, 39, 39), radius=6, fill="white")
    draw.rectangle((22, 34, 42, 39), fill="white")
    draw.rectangle((30, 38, 34, 48), fill="white")
    draw.rectangle((23, 48, 41, 52), fill="white")
    return image
