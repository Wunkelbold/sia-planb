import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "flask-server"))

from Sections.EventScheduleRules import shift_event_schedule


class Record:
    def __init__(self, **values):
        for key, value in values.items():
            setattr(self, key, value)


class EventScheduleTests(unittest.TestCase):
    def setUp(self):
        self.base = datetime(2027, 5, 10, 18, 0)
        self.difference = timedelta(days=2)

    def test_all_related_times_move_by_the_same_delta(self):
        event = Record(end=self.base + timedelta(hours=4))
        shift = Record(start=self.base - timedelta(hours=2), end=self.base)
        window = Record(start=self.base - timedelta(days=3), end=self.base)
        task = Record(
            deadline=self.base - timedelta(hours=1),
            timeframe_start=self.base - timedelta(hours=3),
            timeframe_end=self.base - timedelta(hours=2),
        )

        moved = shift_event_schedule(
            event,
            self.difference,
            shifts=[shift],
            registration_windows=[window],
            tasks=[task],
        )

        self.assertEqual(self.base + timedelta(days=2, hours=4), event.end)
        self.assertEqual(self.base + timedelta(days=2, hours=-2), shift.start)
        self.assertEqual(self.base + timedelta(days=2), shift.end)
        self.assertEqual(self.base + timedelta(days=2), window.end)
        self.assertEqual(self.base - timedelta(days=1), window.start)
        self.assertEqual(self.base + timedelta(days=2, hours=-1), task.deadline)
        self.assertEqual(self.base + timedelta(days=2, hours=-3), task.timeframe_start)
        self.assertEqual(self.base + timedelta(days=2, hours=-2), task.timeframe_end)
        self.assertEqual({"shifts": 1, "registration_windows": 1, "tasks": 1}, moved)

    def test_empty_times_stay_empty(self):
        event = Record(end=None)
        shift = Record(start=None, end=None)
        window = Record(start=None, end=self.base)
        task = Record(deadline=None, timeframe_start=None, timeframe_end=None)

        moved = shift_event_schedule(
            event,
            self.difference,
            shifts=[shift],
            registration_windows=[window],
            tasks=[task],
        )

        self.assertIsNone(event.end)
        self.assertIsNone(shift.start)
        self.assertIsNone(shift.end)
        self.assertIsNone(window.start)
        self.assertEqual(self.base + timedelta(days=2), window.end)
        self.assertIsNone(task.deadline)
        self.assertIsNone(task.timeframe_start)
        self.assertIsNone(task.timeframe_end)
        self.assertEqual({"shifts": 0, "registration_windows": 1, "tasks": 0}, moved)

    def test_negative_delta_moves_everything_back(self):
        event = Record(end=self.base)
        task = Record(deadline=self.base, timeframe_start=None, timeframe_end=None)

        shift_event_schedule(event, -self.difference, tasks=[task])

        self.assertEqual(self.base - timedelta(days=2), event.end)
        self.assertEqual(self.base - timedelta(days=2), task.deadline)


if __name__ == "__main__":
    unittest.main()
