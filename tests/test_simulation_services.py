import pytest
from fastfood.domain.enums import OrderChannel, OrderComplexity, PriorityLevel, TicketStatus, SlaStatus, QueueEventType
from fastfood.domain.order import Order
from fastfood.domain.ticket import Ticket
from fastfood.domain.rules import BusinessRules
from fastfood.queues.priority_queue import PriorityQueue
from fastfood.queues.priority_policy import QuotaFairnessPolicy
from fastfood.services.sla_monitor import SlaMonitor
from fastfood.services.dispatcher import Dispatcher
from fastfood.services.simulation_engine import SimulationEngine


# Mock simples de AuditLogger para os testes não precisarem do banco real da Etapa 6 ainda
class DummyAuditLogger:
    def __init__(self):
        self.events = []

    def record(self, event):
        self.events.append(event)


def test_sla_monitor_wait_and_status():
    rules = BusinessRules()
    monitor = SlaMonitor(rules)

    # Balcão tem limite de SLA de 480 segundos
    order = Order(id="ORD-001", channel=OrderChannel.COUNTER, complexity=OrderComplexity.SIMPLE)
    ticket = Ticket(order=order, arrival_time=0)

    # Tempo 100 segundos (abaixo de 80% do limite de 480s = 384s) -> WAITING
    assert monitor.wait_seconds(ticket, 100) == 100
    assert monitor.status(ticket, 100) == SlaStatus.WAITING

    # Tempo 400 segundos (>= 80% do limite, mas ainda <= 480s) -> AT_RISK
    assert monitor.wait_seconds(ticket, 400) == 400
    assert monitor.status(ticket, 400) == SlaStatus.AT_RISK

    # Tempo 500 segundos (> 480s) sem iniciar -> BREACHED
    assert monitor.wait_seconds(ticket, 500) == 500
    assert monitor.status(ticket, 500) == SlaStatus.BREACHED

    # Iniciando o preparo no segundo 200 (dentro do SLA)
    ticket.start_preparation(200)
    assert monitor.wait_seconds(ticket, 300) == 200
    assert monitor.status(ticket, 300) == SlaStatus.MET


def test_dispatcher_respects_policy_and_station():
    queue = PriorityQueue()
    policy = QuotaFairnessPolicy()
    rules = BusinessRules()
    monitor = SlaMonitor(rules)
    logger = DummyAuditLogger()
    
    dispatcher = Dispatcher(queue, policy, monitor, logger)

    # Enfileira um padrão e um urgente
    order_std = Order(id="STD-1", channel=OrderChannel.COUNTER, complexity=OrderComplexity.SIMPLE)
    order_urg = Order(id="URG-1", channel=OrderChannel.DELIVERY, complexity=OrderComplexity.SIMPLE, courier_waiting=True)

    queue.enqueue(order_std, arrival_time=0)
    queue.enqueue(order_urg, arrival_time=1)

    # Política deve priorizar o urgente primeiro
    started_ticket = dispatcher.start_next(now=2)
    assert started_ticket is not None
    assert started_ticket.priority == PriorityLevel.URGENT
    assert started_ticket.status == TicketStatus.PREPARING


def test_simulation_engine_full_lifecycle():
    queue = PriorityQueue()
    policy = QuotaFairnessPolicy()
    rules = BusinessRules()
    monitor = SlaMonitor(rules)
    logger = DummyAuditLogger()
    dispatcher = Dispatcher(queue, policy, monitor, logger)

    engine = SimulationEngine(dispatcher, queue, rules, logger)

    # 1. Chegada de um pedido de delivery (simples = 60s de preparo)
    order = Order(id="SIM-01", channel=OrderChannel.DELIVERY, complexity=OrderComplexity.SIMPLE, courier_waiting=True)
    ticket = engine.enqueue(order)

    assert engine.current_time == 0
    assert ticket.status == TicketStatus.WAITING

    # 2. Avança 1 segundo: o motor deve despachar automaticamente o pedido para a estação
    snapshot_1 = engine.advance(1)
    assert snapshot_1.current_time == 1
    assert snapshot_1.preparing_ticket is not None
    assert ticket.status == TicketStatus.PREPARING
    assert ticket.start_time == 1

    # O preparo leva 60s, logo termina em 1 + 60 = 61.
    # Avançamos mais 59 segundos (totalizando tempo 60, logo antes de concluir)
    snapshot_60 = engine.advance(59)
    assert snapshot_60.current_time == 60
    assert snapshot_60.preparing_ticket is not None
    assert ticket.status == TicketStatus.PREPARING

    # 3. Avança o 61º segundo: o preparo conclui
    snapshot_61 = engine.advance(1)
    assert snapshot_61.current_time == 61
    assert snapshot_61.preparing_ticket is None
    assert ticket.status == TicketStatus.COMPLETED