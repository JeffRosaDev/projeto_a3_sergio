"""Testes unitários para a integridade básica dos eventos de fila."""

import unittest
from dataclasses import FrozenInstanceError

from fastfood.domain import OrderChannel, PriorityLevel, QueueEvent, QueueEventType


class QueueEventTests(unittest.TestCase):
    """Confere a estrutura imutável que será usada pelo log SQL."""

    def make_event(self, **overrides: object) -> QueueEvent:
        """Monta um evento válido e permite sobrescrever um campo por cenário."""

        values: dict[str, object] = {
            "event_id": "event-1",
            "ticket_id": "ticket-1",
            "event_type": QueueEventType.ENQUEUED,
            "simulated_second": 0,
            "channel": OrderChannel.DELIVERY,
            "priority": PriorityLevel.URGENT,
            "queue_size_before": 0,
            "queue_size_after": 1,
            "queue_snapshot": ("ticket-1",),
        }
        values.update(overrides)
        return QueueEvent(**values)  # type: ignore[arg-type]

    def test_valid_event_keeps_the_waiting_queue_snapshot(self) -> None:
        """O evento preserva um retrato imutável da fila após sua ocorrência."""

        event = self.make_event()
        self.assertEqual(event.queue_snapshot, ("ticket-1",))
        self.assertEqual(event.queue_size_after, len(event.queue_snapshot))
        with self.assertRaises(FrozenInstanceError):
            event.event_id = "changed"  # type: ignore[misc]

    def test_snapshot_length_must_match_queue_size_after(self) -> None:
        """Um snapshot inconsistente é rejeitado antes de chegar à auditoria."""

        with self.assertRaisesRegex(ValueError, "queue_size_after"):
            self.make_event(queue_size_after=2)

    def test_event_time_and_sla_target_must_be_valid(self) -> None:
        """Instantes não podem ser negativos e a meta do SLA deve ser positiva."""

        with self.assertRaisesRegex(ValueError, "simulated_second"):
            self.make_event(simulated_second=-1)
        with self.assertRaisesRegex(ValueError, "sla_target_seconds"):
            self.make_event(sla_target_seconds=0)


if __name__ == "__main__":
    unittest.main()
