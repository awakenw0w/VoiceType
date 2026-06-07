from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import pystray
from PIL import Image, ImageDraw, ImageFilter

from .i18n import status_label, t
from .status import AppStatus


APP_NAME = "VoiceType"

STATUS_COLORS = {
    AppStatus.IDLE: "#8a7652",
    AppStatus.PAUSED: "#8a8379",
    AppStatus.RECORDING: "#c46a54",
    AppStatus.TRANSCRIBING: "#786a54",
    AppStatus.PASTING: "#a98450",
    AppStatus.PASTED: "#8a7652",
    AppStatus.ERROR: "#b24c48",
}


class TrayController:
    def __init__(self, app):
        self._app = app
        self._icon: pystray.Icon | None = None
        self._base_icon = _load_tray_base_icon()

    def run(self) -> None:
        self._icon = pystray.Icon(
            "VoiceType",
            _make_icon(AppStatus.IDLE, self._base_icon),
            APP_NAME,
            self._menu(),
        )

        def setup(icon: pystray.Icon) -> None:
            icon.visible = True
            self._app.on_tray_ready()

        self._icon.run(setup=setup)

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()

    def update_status(self, status: AppStatus, detail: str = "") -> None:
        if not self._icon:
            return
        label = status_label(self._app.config.interface_language, status)
        self._icon.title = f"{APP_NAME} - {label}"
        self._icon.icon = _make_icon(status, self._base_icon)
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
        language = self._app.config.interface_language
        return pystray.Menu(
            pystray.MenuItem(self._pause_label, self._toggle_pause),
            pystray.MenuItem(t(language, "settings"), lambda _icon, _item: self._app.open_settings()),
            pystray.MenuItem(t(language, "reload_settings"), lambda _icon, _item: self._app.reload_settings()),
            pystray.MenuItem(
                t(language, "autostart"),
                lambda _icon, _item: self._app.toggle_autostart(),
                checked=lambda _item: self._app.config.autostart,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(t(language, "exit"), lambda _icon, _item: self._app.stop()),
        )

    def _pause_label(self, _item) -> str:
        language = self._app.config.interface_language
        return t(language, "resume") if self._app.paused else t(language, "pause")

    def _toggle_pause(self, _icon, _item) -> None:
        self._app.toggle_pause()


def _make_icon(status: AppStatus, base_icon: Image.Image | None = None) -> Image.Image:
    if base_icon is None:
        base_icon = _fallback_base_icon()
    image = base_icon.copy().convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
    color = STATUS_COLORS.get(status, STATUS_COLORS[AppStatus.IDLE])
    indicator = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.ellipse((42, 42, 62, 62), fill=(0, 0, 0, 65))
    shadow = shadow.filter(ImageFilter.GaussianBlur(2))
    indicator.alpha_composite(shadow)
    draw = ImageDraw.Draw(indicator)
    draw.ellipse((40, 40, 62, 62), fill=(255, 255, 255, 245))
    draw.ellipse((44, 44, 58, 58), fill=color)
    image.alpha_composite(indicator)
    return image


def _load_tray_base_icon() -> Image.Image | None:
    for relative in (
        Path("brand") / "voicetype-64.png",
        Path("brand") / "voicetype-256.png",
        Path("ui") / "voicetype-logo-64.png",
        Path("ui") / "voicetype-icon.png",
        Path("logo2.png"),
    ):
        path = _asset_path(relative)
        if not path:
            continue
        try:
            return Image.open(path).convert("RGBA")
        except Exception:
            continue
    return None


def _fallback_base_icon() -> Image.Image:
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((4, 4, 60, 60), radius=14, fill=(255, 255, 255, 255))
    draw.line((18, 20, 31, 44, 46, 18), fill="#1b1c1c", width=6, joint="curve")
    for x, h in ((39, 16), (45, 26), (51, 18)):
        draw.rounded_rectangle((x, 32 - h // 2, x + 4, 32 + h // 2), radius=2, fill="#d4bd92")
    return image


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
