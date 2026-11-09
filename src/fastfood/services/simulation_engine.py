# src/fastfood/services/simulation_engine.py

import uuid
from dataclasses import dataclass
from fastfood.domain.enums import TicketStatus, QueueEventType
from fastfood.domain.events import QueueEvent

@dataclass
class SimulationSnapshot:
    current_time: int
    preparing_ticket: object | None
    queue_snapshot: list

class SimulationEngine:
    def __init__(self, dispatcher, queue, rules, audit_logger):
        self.dispatcher = dispatcher
        self.queue = queue
        self.rules = rules
        self.audit_logger = audit_logger
        self.current_time = 0
        self.preparing_ticket = None
        self.preparation_end_time = 0

    def enqueue(self, order):
        # Registra o estado da fila antes da inserção
        queue_size_before = len(self.queue.snapshot())
        
        # Envia o pedido para a fila (a PriorityQueue irá criar e retornar o Ticket)
        ticket = self.queue.enqueue(order, self.current_time)
        
        # Registra o estado após a inserção para o evento de auditoria
        queue_size_after = len(self.queue.snapshot())
        snapshot_tuple = tuple(t.order.id for t in self.queue.snapshot())
        sla_target = self.rules.sla_seconds_for(order.channel)
        
        # Emite o evento tipado ENQUEUED com os dados validados
        event = QueueEvent(
            event_id=str(uuid.uuid4()),
            ticket_id=ticket.order.id,
            event_type=QueueEventType.ENQUEUED,
            simulated_second=self.current_time,
            channel=order.channel,
            priority=ticket.priority,
            queue_size_before=queue_size_before,
            queue_size_after=queue_size_after,
            queue_snapshot=snapshot_tuple,
            wait_seconds=None,
            sla_target_seconds=sla_target,
            sla_status=None
        )
        self.audit_logger.record(event)
        
        return ticket

    def advance(self, seconds: int) -> SimulationSnapshot:
        target_time = self.current_time + seconds
        
        # O relógio é simulado segundo a segundo[cite: 1]
        while self.current_time < target_time:
            self.current_time += 1
            
            # Se o tempo de preparo terminou, libera a estação[cite: 1]
            if self.preparing_ticket and self.current_time >= self.preparation_end_time:
                self.preparing_ticket.status = TicketStatus.COMPLETED
                self.preparing_ticket = None
                
            # Se a estação está livre, solicita o próximo pedido ao Dispatcher[cite: 1]
            if not self.preparing_ticket:
                next_ticket = self.dispatcher.start_next(self.current_time)
                if next_ticket:
                    self.preparing_ticket = next_ticket
                    prep_time = self.rules.preparation_seconds_for(next_ticket.order.complexity)
                    self.preparation_end_time = self.current_time + prep_time

        return SimulationSnapshot(
            current_time=self.current_time,
            preparing_ticket=self.preparing_ticket,
            queue_snapshot=self.queue.snapshot()
        )