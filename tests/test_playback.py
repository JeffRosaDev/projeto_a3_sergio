"""Regressões do relógio sob cliques frequentes, pausas e atrasos de rede."""

import sqlite3
import unittest
from unittest.mock import patch

from fastfood.services.playback import PlaybackClock, advance_playback
from fastfood.services.scenarios import create_engine


class PlaybackTests(unittest.TestCase):
    """Tempo só é consumido uma vez; chegadas e avanço compartilham transação."""

    def test_frequent_redraws_accumulate_instead_of_starving_clock(self):
        clock = PlaybackClock(100.0)
        advances = [
            clock.consume(t, 5)
            for t in (100.2, 100.4, 100.8, 101.2, 101.4, 101.8, 102.1)
        ]
        self.assertEqual(sum(advances), 10)
        self.assertEqual(clock.consume(102.1, 5), 0)
        self.assertEqual(clock.consume(103.0, 5), 5)

    def test_resume_does_not_count_pause_or_old_speed(self):
        clock = PlaybackClock(0.0)
        self.assertEqual(clock.consume(1.4, 5), 5)
        clock.reset(100.0)
        self.assertEqual(clock.consume(100.5, 60), 0)
        self.assertEqual(clock.consume(101.0, 60), 60)

    def test_sleep_recovery_is_bounded(self):
        clock = PlaybackClock(0.0)
        self.assertEqual(clock.consume(3600.2, 60), 300)
        self.assertEqual(clock.consume(3600.5, 60), 0)
        self.assertEqual(clock.consume(3601.0, 60), 60)

    def test_invalid_clock_and_speed(self):
        for now, speed in [(float("nan"), 5), (float("inf"), 5), (10, True), (10, 2)]:
            with self.subTest(now=now, speed=speed), self.assertRaises(ValueError):
                PlaybackClock(0).consume(now, speed)

    def test_periodic_arrivals_and_rollback(self):
        engine = create_engine()
        self.addCleanup(engine.audit_logger.close)
        options = dict(arrivals=True, interval=3, seed=42, urgent_percent=100)
        advance_playback(engine, 10, **options)
        self.assertEqual(engine.current_time, 10)
        self.assertEqual([t.enqueued_at for t in engine.tickets.values()], [3, 6, 9])
        self.assertEqual(engine.tickets["PED-0001"].started_at, 4)
        before = engine.audit_logger.export_sql()
        with patch(
            "fastfood.services.playback.add_burst",
            side_effect=sqlite3.OperationalError("disk full"),
        ):
            with self.assertRaises(sqlite3.OperationalError):
                advance_playback(engine, 5, **options)
        self.assertEqual(engine.current_time, 10)
        self.assertEqual(engine.audit_logger.export_sql(), before)

    def test_physical_pause_keeps_arrivals_and_wait_growing(self):
        engine = create_engine()
        self.addCleanup(engine.audit_logger.close)
        engine.pause_station(True)
        advance_playback(
            engine, 10, arrivals=True, interval=2, seed=42, urgent_percent=100
        )
        self.assertEqual(len(engine.queue.snapshot()), 5)
        self.assertIsNone(engine.preparing_ticket)
        self.assertEqual(engine.current_time, 10)
