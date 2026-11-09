"""Motor da simulação segundo a segundo com fila de prioridade e SLA."""

from dataclasses import dataclass
from typing import Any
import uuid

from fastfood.domain.enums import QueueEventType, TicketStatus
from fastfood.domain.events import QueueEvent
from fastfood.domain.order import Order
from fastfood.domain.ticket import Ticket


@dataclass
class SimulationSnapshot:
    """Retrato do estado da simulação em um determinado segundo simulado."""

    current_time: int
    preparing_ticket: Any | None
    queue_snapshot: list[Any]


class SimulationEngine:
    """Controla o relógio simulado, a estação de preparo e o histórico de auditoria."""

    def __init__(self, dispatcher, queue, rules, audit_logger) -> None:
        self.dispatcher = dispatcher
        self.queue = queue
        self.rules = rules
        self.audit_logger = audit_logger
        self.current_time = 0
        self.preparing_ticket = None
        self.preparation_end_time = 0
        self._sequence_counter = 0

    def enqueue(self, item: Order | Ticket) -> Ticket:
        """Adiciona um pedido ou ticket à fila no segundo simulado atual.

        Cria o Ticket com número de sequência e regras de negócio se um Order
        for fornecido, enfileira na PriorityQueue e registra o evento ENQUEUED
        na auditoria SQL.
        """
        if isinstance(item, Order):
            self._sequence_counter += 1
            ticket = Ticket(
                order=item,
                sequence=self._sequence_counter,
                rules=self.rules,
            )
        elif isinstance(item, Ticket):
            ticket = item
        else:
            raise TypeError("item deve ser Order ou Ticket.")

        queue_size_before = len(self.queue.snapshot())
        self.queue.enqueue(ticket)
        queue_size_after = len(self.queue.snapshot())

        snapshot_tuple = tuple(t.order.id for t in self.queue.snapshot())
        sla_target = self.rules.sla_seconds_for(ticket.order.channel)

        event = QueueEvent(
            event_id=str(uuid.uuid4()),
            ticket_id=ticket.order.id,
            event_type=QueueEventType.ENQUEUED,
            simulated_second=self.current_time,
            channel=ticket.order.channel,
            priority=ticket.priority,
            queue_size_before=queue_size_before,
            queue_size_after=queue_size_after,
            queue_snapshot=snapshot_tuple,
            wait_seconds=None,
            sla_target_seconds=sla_target,
            sla_status=None,
        )
        self.audit_logger.record(event)

        return ticket

    def advance(self, seconds: int) -> SimulationSnapshot:
        """Avança o relógio simulado e processa inícios e conclusões de preparo."""
        if isinstance(seconds, bool) or not isinstance(seconds, int):
            raise TypeError("seconds deve ser um inteiro.")
        if seconds < 0:
            raise ValueError("seconds não pode ser negativo.")

        target_time = self.current_time + seconds

        while self.current_time < target_time:
            self.current_time += 1

            # 1. Conclusão de preparo pendente
            if self.preparing_ticket and self.current_time >= self.preparation_end_time:
                completed = self.preparing_ticket
                if hasattr(completed, "complete_preparation"):
                    completed.complete_preparation(self.current_time)
                else:
                    completed.status = TicketStatus.COMPLETED

                # Registra evento de conclusão na auditoria
                queue_snapshot = self.queue.snapshot()
                event = QueueEvent(
                    event_id=str(uuid.uuid4()),
                    ticket_id=completed.order.id,
                    event_type=QueueEventType.PREPARATION_COMPLETED,
                    simulated_second=self.current_time,
                    channel=completed.order.channel,
                    priority=completed.priority,
                    queue_size_before=len(queue_snapshot),
                    queue_size_after=len(queue_snapshot),
                    queue_snapshot=tuple(t.order.id for t in queue_snapshot),
                    wait_seconds=self.dispatcher.sla_monitor.wait_seconds(
                        completed, self.current_time
                    ),
                    sla_target_seconds=self.rules.sla_seconds_for(completed.order.channel),
                    sla_status=self.dispatcher.sla_monitor.status(
                        completed, self.current_time
                    ),
                )
                self.audit_logger.record(event)
                self.preparing_ticket = None

            # 2. Despacho se a estação estiver livre
            if not self.preparing_ticket:
                next_ticket = self.dispatcher.start_next(self.current_time)
                if next_ticket:
                    self.preparing_ticket = next_ticket
                    prep_time = self.rules.preparation_seconds_for(
                        next_ticket.order.complexity
                    )
                    self.preparation_end_time = self.current_time + prep_time

        return SimulationSnapshot(
            current_time=self.current_time,
            preparing_ticket=self.preparing_ticket,
            queue_snapshot=self.queue.snapshot(),
        )
