import tempfile
import unittest
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

from win_whisper_dictation.stats import DictationStats, StatsManager, _next_streak, count_words


class StatsTests(unittest.TestCase):
    def test_count_words_supports_russian_and_english(self):
        self.assertEqual(count_words("Hello world. \u041f\u0440\u0438\u0432\u0435\u0442 \u043c\u0438\u0440"), 4)

    def test_count_words_ignores_numbered_list_markers(self):
        self.assertEqual(count_words("1. Buy milk\n2. Call Alex"), 4)

    def test_record_dictation_updates_local_totals(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = StatsManager(Path(temp_dir) / "stats.json")
            stats = manager.record_dictation("Hello world again", duration_seconds=6)
            loaded = StatsManager(Path(temp_dir) / "stats.json").stats

        self.assertEqual(stats.words_dictated, 3)
        self.assertEqual(stats.dictation_sessions, 1)
        self.assertAlmostEqual(stats.words_per_minute, 30.0)
        self.assertEqual(loaded.words_dictated, 3)

    def test_streak_continues_for_consecutive_days(self):
        today = date.today()
        yesterday = today - timedelta(days=1)

        self.assertEqual(_next_streak(yesterday.isoformat(), 2, today), 3)

    def test_streak_resets_after_gap(self):
        today = date.today()
        old = today - timedelta(days=3)

        self.assertEqual(_next_streak(old.isoformat(), 4, today), 1)

    def test_same_day_keeps_current_streak(self):
        today = date.today()
        stats = replace(DictationStats(), current_streak=5, last_dictation_date=today.isoformat())

        self.assertEqual(_next_streak(stats.last_dictation_date, stats.current_streak, today), 5)


if __name__ == "__main__":
    unittest.main()
