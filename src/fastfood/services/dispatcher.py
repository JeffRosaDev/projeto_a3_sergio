"""Despachante responsável por selecionar e iniciar o próximo pedido."""

import uuid
from typing import Any

from fastfood.domain.enums import QueueEventType, TicketStatus
from fastfood.domain.events import QueueEvent


class Dispatcher:
    """Coordena a fila, a política de justiça e o início do preparo dos tickets."""

    def __init__(self, queue, policy, sla_monitor, audit_logger) -> None:
        self.queue = queue
        self.policy = policy
        self.sla_monitor = sla_monitor
        self.audit_logger = audit_logger

    def start_next(self, now: int) -> Any:
        """Inicia o próximo pedido elegível pela política de justiça.

        Retira o ticket mais antigo da faixa escolhida, altera o estado
        para PREPARING, registra o evento na auditoria e retorna o ticket.
        """
        priority = self.policy.choose_priority(self.queue)
        if not priority:
            return None

        queue_size_before = self._total_queue_size()
        ticket = self.queue.pop_oldest(priority)
        self.policy.record_started(priority)

        # Transição de estado formal usando o método do Ticket
        if hasattr(ticket, "start_preparation"):
            ticket.start_preparation(now)
        else:
            ticket.status = TicketStatus.PREPARING
            ticket.started_at = now

        # Para compatibilidade com eventuais códigos que leiam start_time
        try:
            object.__setattr__(ticket, "start_time", now)
        except Exception:
            pass

        queue_size_after = self._total_queue_size()
        snapshot_tuple = tuple(t.order.id for t in self.queue.snapshot())

        sla_stat = self.sla_monitor.status(ticket, now)
        wait_time = self.sla_monitor.wait_seconds(ticket, now)
        sla_target = self.sla_monitor.rules.sla_seconds_for(ticket.order.channel)

        event = QueueEvent(
            event_id=str(uuid.uuid4()),
            ticket_id=ticket.order.id,
            event_type=QueueEventType.SERVICE_STARTED,
            simulated_second=now,
            channel=ticket.order.channel,
            priority=priority,
            queue_size_before=queue_size_before,
            queue_size_after=queue_size_after,
            queue_snapshot=snapshot_tuple,
            wait_seconds=wait_time,
            sla_target_seconds=sla_target,
            sla_status=sla_stat,
        )
        self.audit_logger.record(event)

        return ticket

    def _total_queue_size(self) -> int:
        return len(self.queue.snapshot())
