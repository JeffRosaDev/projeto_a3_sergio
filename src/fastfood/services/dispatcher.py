"""Seleção de faixa e início transacional de um pedido."""

from uuid import uuid4

from fastfood.domain.enums import QueueEventType
from fastfood.domain.events import QueueEvent


class Dispatcher:
    """Colabora com fila, política, monitor e auditoria por injeção de dependências."""

    def __init__(self, queue, policy, sla_monitor, audit_logger):
        """Recebe os mesmos colaboradores usados pelo motor."""
        self.queue, self.policy = queue, policy
        self.sla_monitor, self.audit_logger = sla_monitor, audit_logger

    def start_next(self, now):
        """Inicia o mais antigo da faixa escolhida; restaura tudo se o SQL falhar."""
        priority = self.policy.choose_priority(self.queue)
        if priority is None:
            return None
        before = self.queue.snapshot()  # Checkpoint preserva identidade dos tickets.
        ticket = next(t for t in before if t.priority is priority)
        policy_state = self.policy.checkpoint()
        state = ticket.status, ticket.started_at
        try:
            with self.audit_logger.transaction():
                ticket.start_preparation(now)
                self.queue.pop_oldest(priority)
                self.policy.record_started(priority)
                after = self.queue.snapshot()
                self.audit_logger.record(
                    QueueEvent(
                        str(uuid4()),
                        ticket.id,
                        QueueEventType.SERVICE_STARTED,
                        now,
                        ticket.order.channel,
                        ticket.priority,
                        len(before),
                        len(after),
                        tuple(t.id for t in after),
                        self.sla_monitor.wait_seconds(ticket, now),
                        ticket.rules.sla_seconds_for(ticket.order.channel),
                        self.sla_monitor.status(ticket, now),
                    )
                )
        except BaseException:
            ticket.status, ticket.started_at = state
            self.queue.restore(before)
            self.policy.restore(policy_state)
            raise
        return ticket
