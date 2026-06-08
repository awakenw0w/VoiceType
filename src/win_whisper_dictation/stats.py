from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, replace
from datetime import date, timedelta
from pathlib import Path


@dataclass(frozen=True)
class DictationStats:
    words_dictated: int = 0
    dictation_sessions: int = 0
    total_recording_seconds: float = 0.0
    current_streak: int = 0
    last_dictation_date: str = ""

    @property
    def words_per_minute(self) -> float:
        if self.total_recording_seconds <= 0:
            return 0.0
        return self.words_dictated / (self.total_recording_seconds / 60.0)


class StatsManager:
    def __init__(self, path: Path):
        self.path = path
        self._stats = self.load()

    @property
    def stats(self) -> DictationStats:
        return self._stats

    def load(self) -> DictationStats:
        if not self.path.exists():
            return DictationStats()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return DictationStats()

        stats = DictationStats()
        for key in asdict(stats):
            if key in data:
                stats = replace(stats, **{key: data[key]})
        return stats

    def record_dictation(self, text: str, duration_seconds: float) -> DictationStats:
        word_count = count_words(text)
        if word_count <= 0:
            return self._stats

        today = date.today()
        streak = _next_streak(self._stats.last_dictation_date, self._stats.current_streak, today)
        self._stats = replace(
            self._stats,
            words_dictated=self._stats.words_dictated + word_count,
            dictation_sessions=self._stats.dictation_sessions + 1,
            total_recording_seconds=self._stats.total_recording_seconds + max(0.1, float(duration_seconds)),
            current_streak=streak,
            last_dictation_date=today.isoformat(),
        )
        self.save()
        return self._stats

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(asdict(self._stats), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def stats_path_for_config(config_path: Path) -> Path:
    return config_path.with_name("stats.json")


def count_words(text: str) -> int:
    return len(
        re.findall(
            r"(?=[\w\u0400-\u04ff'-]*[A-Za-z\u0400-\u04ff])[\w\u0400-\u04ff]+(?:[-'][\w\u0400-\u04ff]+)?",
            text,
            flags=re.UNICODE,
        )
    )


def _next_streak(previous_date: str, current_streak: int, today: date) -> int:
    try:
        last = date.fromisoformat(previous_date)
    except ValueError:
        return 1

    if last == today:
        return max(1, current_streak)
    if last == today - timedelta(days=1):
        return max(0, current_streak) + 1
    return 1
