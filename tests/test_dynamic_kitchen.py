"""Regressão, falhas de persistência e cenários curiosos da cozinha dinâmica."""

import random
import sqlite3
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from unittest.mock import patch

from fastfood.domain.enums import (
    OrderChannel,
    OrderComplexity,
    PriorityLevel,
    SlaStatus,
    TicketStatus,
)
from fastfood.domain.order import Order
from fastfood.services.scenarios import add_burst, create_engine, metrics


class DynamicKitchenTests(unittest.TestCase):
    """Cada teste usa sessão independente, sem escrever nos bancos do usuário."""

    def setUp(self):
        self.engine = create_engine()
        self.addCleanup(self.engine.audit_logger.close)

    def order(self, name="A", channel="counter", complexity="simple", courier=False):
        return self.engine.enqueue(
            Order(name, channel, complexity, self.engine.current_time, courier)
        )

    def test_invalid_times_duplicates_and_cancelled_ids(self):
        t = self.order()
        for value in [-1, True, 1.2, "10", 86401]:
            with self.subTest(value=value), self.assertRaises((ValueError, TypeError)):
                self.engine.advance(value)
        for arrival in [1, 100]:
            with self.assertRaises(ValueError):
                self.engine.enqueue(Order("future", "counter", "simple", arrival))
        self.engine.cancel(t.id)
        with self.assertRaises(ValueError):
            self.order()
        self.assertEqual(self.engine.current_time, 0)
        self.assertEqual(self.engine.audit_logger.count(), 2)

    def test_configuration_preserves_contract_and_active_preparation(self):
        first = self.order("first", "delivery", courier=True)
        self.engine.advance(1)
        rules = replace(
            self.engine.rules,
            sla_targets_seconds={c: 5 for c in OrderChannel},
            preparation_times_seconds={c: 10 for c in OrderComplexity},
            prioritize_delivery=False,
            urgent_quota=1,
        )
        self.engine.configure(rules)
        second = self.order("second", "delivery", courier=True)
        self.assertEqual(first.rules.sla_seconds_for("delivery"), 180)
        self.assertEqual(second.rules.sla_seconds_for("delivery"), 5)
        self.assertEqual(first.priority, PriorityLevel.URGENT)
        self.assertEqual(second.priority, PriorityLevel.STANDARD)
        self.assertEqual(self.engine.preparation_end_time, 61)
        self.engine.advance(60)
        self.assertEqual(self.engine.preparation_end_time, 71)
        self.assertEqual(
            self.engine.dispatcher.sla_monitor.status(second, 61), SlaStatus.BREACHED
        )

    def test_pause_and_manual_recovery(self):
        first = self.order()
        self.engine.advance(1)
        self.engine.pause_station(True)
        self.engine.advance(100)
        self.assertEqual(self.engine.preparation_end_time, 161)
        self.assertEqual(first.status, TicketStatus.PREPARING)
        self.engine.adjust_remaining(5)
        self.engine.pause_station(False)
        self.engine.advance(5)
        self.assertEqual(first.completed_at, 106)
        self.assertEqual(metrics(self.engine)["mean_wait"], 1)

    def test_empty_pause_resume_and_bad_adjustments(self):
        self.engine.pause_station(True)
        self.order()
        self.engine.advance(900)
        self.assertIsNone(self.engine.preparing_ticket)
        with self.assertRaises(ValueError):
            self.engine.adjust_remaining(0)
        self.engine.pause_station(False)
        self.engine.advance(1)
        self.assertEqual(self.engine.preparing_ticket.started_at, 901)
        with self.assertRaises(ValueError):
            self.engine.cancel("A")
        with self.assertRaises(ValueError):
            self.engine.cancel("missing")

    def test_rollback_memory_and_sql_on_event_failure(self):
        first = self.order()
        logger = self.engine.audit_logger
        original = logger.record

        def fail_on_start(event):
            original(event)
            raise sqlite3.OperationalError("injected failure after insert")

        with patch.object(logger, "record", side_effect=fail_on_start):
            with self.assertRaises(sqlite3.OperationalError):
                self.engine.advance(61)
            with self.assertRaises(sqlite3.OperationalError):
                self.order("B")
            with self.assertRaises(sqlite3.OperationalError):
                self.engine.cancel("A")
        self.assertEqual(logger.count(), 1)
        self.assertEqual(self.engine.current_time, 0)
        self.assertEqual(first.status, TicketStatus.WAITING)
        self.assertEqual(list(self.engine.tickets), ["A"])
        self.assertEqual(self.engine.queue.snapshot(), [first])
        self.engine.advance(61)
        self.assertEqual(first.status, TicketStatus.COMPLETED)

    def test_rollback_config_and_complete_then_start(self):
        first = self.order("A")
        self.order("B")
        self.engine.advance(1)
        old = self.engine.rules
        with patch.object(
            self.engine.audit_logger,
            "record_action",
            side_effect=sqlite3.OperationalError("disk"),
        ):
            with self.assertRaises(sqlite3.OperationalError):
                self.engine.configure(replace(old, urgent_quota=1))
        self.assertIs(self.engine.rules, old)
        original = self.engine.audit_logger.record

        def fail_second(event):
            if event.ticket_id == "B":
                raise sqlite3.OperationalError("disk")
            original(event)

        with patch.object(self.engine.audit_logger, "record", side_effect=fail_second):
            with self.assertRaises(sqlite3.OperationalError):
                self.engine.advance(60)
        self.assertEqual(first.status, TicketStatus.PREPARING)
        self.assertEqual(self.engine.current_time, 1)
        self.assertEqual(self.engine.audit_logger.count(), 3)

    def test_sql_roundtrip_global_order_and_append_only(self):
        self.order("O'Brien <script>")
        self.engine.configure(replace(self.engine.rules, urgent_quota=2))
        self.engine.advance(61)
        with sqlite3.connect(":memory:") as db:
            db.executescript(self.engine.audit_logger.export_sql())
            for table in ["queue_events", "simulation_actions", "audit_sequence"]:
                original = self.engine.audit_logger._connection.execute(
                    f"SELECT * FROM {table} ORDER BY rowid"
                ).fetchall()
                self.assertEqual(
                    [tuple(r) for r in original],
                    db.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall(),
                )
                for verb in ["DELETE FROM", "UPDATE"]:
                    sql = (
                        f"{verb} {table}"
                        if verb.startswith("DELETE")
                        else f"UPDATE {table} SET rowid=rowid"
                    )
                    with self.assertRaises(sqlite3.IntegrityError):
                        db.execute(sql)

    def test_thresholds_and_no_preparation_in_wait(self):
        t = self.order("d", "delivery", courier=True)
        monitor = self.engine.dispatcher.sla_monitor
        for now, status in [
            (143, SlaStatus.WAITING),
            (144, SlaStatus.AT_RISK),
            (180, SlaStatus.AT_RISK),
            (181, SlaStatus.BREACHED),
        ]:
            self.assertEqual(monitor.status(t, now), status)
        t.start_preparation(0)
        self.assertEqual(monitor.wait_seconds(t, 999), 0)
        self.assertEqual(monitor.status(t, 999), SlaStatus.MET)

    def test_saturated_quota_lowered_without_forgetting_history(self):
        add_burst(self.engine, 7, scenario="Justiça 3:1")
        self.engine.advance(61)
        self.engine.configure(replace(self.engine.rules, urgent_quota=1))
        self.engine.advance(60)
        self.assertEqual(self.engine.preparing_ticket.priority, PriorityLevel.STANDARD)

    def test_reproducible_bursts_and_session_isolation(self):
        other = create_engine()
        self.addCleanup(other.audit_logger.close)
        for engine in [self.engine, other]:
            add_burst(engine, 100, seed=97)

        def profiles(engine):
            return [
                (t.order.channel, t.order.complexity) for t in engine.tickets.values()
            ]

        self.assertEqual(profiles(self.engine), profiles(other))
        self.engine.advance(3600)
        self.assertEqual(other.current_time, 0)
        self.assertEqual(other.audit_logger.count(), 100)

    def test_random_operations_invariants(self):
        rng = random.Random(2781)
        for i in range(350):
            choice = rng.randrange(5)
            if choice == 0:
                self.order(
                    str(i),
                    rng.choice(["delivery", "counter", "pickup"]),
                    rng.choice(["simple", "medium", "complex"]),
                    True,
                )
            elif choice == 1:
                self.engine.advance(rng.randrange(200))
            elif choice == 2:
                self.engine.configure(
                    replace(self.engine.rules, urgent_quota=rng.randint(1, 8))
                )
            elif choice == 3 and self.engine.queue.snapshot():
                self.engine.cancel(rng.choice(self.engine.queue.snapshot()).id)
            else:
                self.engine.pause_station(rng.choice([True, False]))
            waiting = self.engine.queue.snapshot()
            self.assertEqual(len(waiting), len(set(t.id for t in waiting)))
            self.assertTrue(all(t.status == TicketStatus.WAITING for t in waiting))
            self.assertLessEqual(
                sum(
                    t.status == TicketStatus.PREPARING
                    for t in self.engine.tickets.values()
                ),
                1,
            )
        self.engine.pause_station(False)
        self.engine.advance(86400)
        self.assertFalse(self.engine.queue.snapshot())
        self.assertIsNone(self.engine.preparing_ticket)

    def test_logger_works_across_streamlit_rerun_threads(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(
                pool.map(
                    lambda i: self.engine.audit_logger.record_action(
                        i, "TEST", {"i": i}
                    ),
                    range(50),
                )
            )
        self.assertEqual(len(self.engine.audit_logger.actions()), 51)


if __name__ == "__main__":
    unittest.main()
