"""Testes da política de justiça com a fila e os tickets do projeto."""

import unittest

from fastfood.domain.enums import PriorityLevel, TicketStatus
from fastfood.domain.order import Order
from fastfood.domain.rules import BusinessRules
from fastfood.domain.ticket import Ticket
from fastfood.queues.priority_policy import QuotaFairnessPolicy
from fastfood.queues.priority_queue import PriorityQueue


class QuotaFairnessPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.queue = PriorityQueue()
        self.policy = QuotaFairnessPolicy()
        self.sequence = 0

    def enqueue(self, *, urgent: bool, arrival_time: int = 0) -> Ticket:
        self.sequence += 1
        order = Order(
            f"PED-{self.sequence}",
            "delivery" if urgent else "counter",
            "simple",
            arrival_time=arrival_time,
            courier_waiting=urgent,
        )
        ticket = Ticket(order, sequence=self.sequence)
        self.queue.enqueue(ticket)
        return ticket

    def start_next(self, now: int) -> Ticket:
        priority = self.policy.choose_priority(self.queue)
        if priority is None:
            self.fail("Esperava um ticket aguardando atendimento.")
        ticket = self.queue.pop_oldest(priority)
        ticket.start_preparation(now)
        self.policy.record_started(ticket.priority)
        return ticket

    def test_empty_queue_has_no_priority(self) -> None:
        self.assertIsNone(self.policy.choose_priority(self.queue))

    def test_standard_is_selected_when_there_are_no_urgent_tickets(self) -> None:
        self.enqueue(urgent=False)

        self.assertIs(self.policy.choose_priority(self.queue), PriorityLevel.STANDARD)

    def test_repeated_choices_do_not_consume_quota_or_change_tickets(self) -> None:
        urgent = self.enqueue(urgent=True)
        standard = self.enqueue(urgent=False)

        for _ in range(5):
            self.assertIs(self.policy.choose_priority(self.queue), PriorityLevel.URGENT)

        self.assertEqual(self.queue.snapshot(), [urgent, standard])
        self.assertIs(urgent.status, TicketStatus.WAITING)
        self.assertIs(standard.status, TicketStatus.WAITING)

    def test_standard_starts_after_three_urgent_with_a_large_backlog(self) -> None:
        standard = self.enqueue(urgent=False)
        urgent = [self.enqueue(urgent=True) for _ in range(100)]

        started = [self.start_next(now) for now in (0, 60, 120, 180)]

        self.assertEqual(started, [*urgent[:3], standard])
        self.assertEqual(self.queue.snapshot(), urgent[3:])
        self.assertIs(standard.status, TicketStatus.PREPARING)

    def test_urgent_lane_keeps_moving_and_a_late_standard_is_selected_next(self) -> None:
        urgent = [self.enqueue(urgent=True) for _ in range(7)]
        for index in range(6):
            self.assertIs(self.start_next(index * 60), urgent[index])

        standard = self.enqueue(urgent=False, arrival_time=331)

        self.assertIs(self.start_next(360), standard)
        self.assertIs(self.start_next(420), urgent[6])

    def test_starting_standard_resets_the_configured_quota(self) -> None:
        self.policy = QuotaFairnessPolicy(BusinessRules(urgent_quota=2))
        standard = [self.enqueue(urgent=False) for _ in range(2)]
        urgent = [self.enqueue(urgent=True) for _ in range(5)]

        started = [self.start_next(now) for now in range(0, 360, 60)]

        self.assertEqual(started, [*urgent[:2], standard[0], *urgent[2:4], standard[1]])
