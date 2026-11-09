# src/fastfood/services/dispatcher.py

import uuid
from fastfood.domain.enums import TicketStatus, QueueEventType
from fastfood.domain.events import QueueEvent

class Dispatcher:
    def __init__(self, queue, policy, sla_monitor, audit_logger):
        self.queue = queue
        self.policy = policy
        self.sla_monitor = sla_monitor
        self.audit_logger = audit_logger

    def start_next(self, now: int):
        # 1. Pede à política de prioridade para escolher a próxima faixa
        priority = self.policy.choose_priority(self.queue)
        if not priority:
            return None

        # Registra o tamanho da fila antes de retirar o ticket
        queue_size_before = self._total_queue_size()
        
        # 2. Retira o ticket mais antigo da faixa escolhida
        ticket = self.queue.pop_oldest(priority)
        self.policy.record_started(priority)

        # 3. Atualiza os dados do ticket para o início do preparo
        ticket.status = TicketStatus.PREPARING
        ticket.start_time = now
        
        # Prepara os dados exigidos pelo QueueEvent da auditoria
        queue_size_after = self._total_queue_size()
        snapshot_tuple = tuple(t.order.id for t in self.queue.snapshot())
        
        sla_stat = self.sla_monitor.status(ticket, now)
        wait_time = self.sla_monitor.wait_seconds(ticket, now)
        sla_target = self.sla_monitor.rules.sla_seconds_for(ticket.order.channel)

        # 4. Emite o evento tipado rigoroso para o módulo de auditoria
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
            sla_status=sla_stat
        )
        self.audit_logger.record(event)
        
        return ticket

    def _total_queue_size(self) -> int:
        return len(self.queue.snapshot())