"""Testes unitários dos serviços de simulação, SLA e despacho."""

import unittest

from fastfood.audit.audit_logger import AuditLogger
from fastfood.domain.enums import (
    OrderChannel,
    OrderComplexity,
    PriorityLevel,
    QueueEventType,
    SlaStatus,
    TicketStatus,
)
from fastfood.domain.order import Order
from fastfood.domain.rules import BusinessRules
from fastfood.domain.ticket import Ticket
from fastfood.queues.priority_policy import QuotaFairnessPolicy
from fastfood.queues.priority_queue import PriorityQueue
from fastfood.services.dispatcher import Dispatcher
from fastfood.services.simulation_engine import SimulationEngine
from fastfood.services.sla_monitor import SlaMonitor


class TestSimulationServices(unittest.TestCase):
    """Testes dos serviços integrados com auditoria e domínio."""

    def test_sla_monitor_wait_and_status(self) -> None:
        """Verifica a medição de espera e transições de status de SLA."""
        rules = BusinessRules()
        monitor = SlaMonitor(rules)

        order = Order(
            id="ORD-001",
            channel=OrderChannel.COUNTER,
            complexity=OrderComplexity.SIMPLE,
            arrival_time=0,
        )
        ticket = Ticket(order=order, sequence=1, rules=rules)

        # 100s: espera < 80% de 480s (384s) -> WAITING
        self.assertEqual(monitor.wait_seconds(ticket, 100), 100)
        self.assertEqual(monitor.status(ticket, 100), SlaStatus.WAITING)

        # 400s: espera >= 384s e <= 480s -> AT_RISK
        self.assertEqual(monitor.wait_seconds(ticket, 400), 400)
        self.assertEqual(monitor.status(ticket, 400), SlaStatus.AT_RISK)

        # 500s: espera > 480s sem iniciar -> BREACHED
        self.assertEqual(monitor.wait_seconds(ticket, 500), 500)
        self.assertEqual(monitor.status(ticket, 500), SlaStatus.BREACHED)

        # Início de preparo aos 200s (dentro do limite) -> MET
        ticket.start_preparation(200)
        self.assertEqual(monitor.wait_seconds(ticket, 300), 200)
        self.assertEqual(monitor.status(ticket, 300), SlaStatus.MET)

    def test_dispatcher_respects_policy_and_records_audit(self) -> None:
        """Despachante consulta política, inicia preparo e registra no AuditLogger."""
        queue = PriorityQueue()
        policy = QuotaFairnessPolicy()
        rules = BusinessRules()
        monitor = SlaMonitor(rules)
        logger = AuditLogger(db_path=":memory:")

        dispatcher = Dispatcher(queue, policy, monitor, logger)

        order_std = Order(
            id="STD-1",
            channel=OrderChannel.COUNTER,
            complexity=OrderComplexity.SIMPLE,
            arrival_time=0,
        )
        order_urg = Order(
            id="URG-1",
            channel=OrderChannel.DELIVERY,
            complexity=OrderComplexity.SIMPLE,
            arrival_time=1,
            courier_waiting=True,
        )

        ticket_std = Ticket(order=order_std, sequence=1, rules=rules)
        ticket_urg = Ticket(order=order_urg, sequence=2, rules=rules)

        queue.enqueue(ticket_std)
        queue.enqueue(ticket_urg)

        # Despachante deve selecionar o urgente primeiro pela política
        started = dispatcher.start_next(now=2)
        self.assertIsNotNone(started)
        self.assertEqual(started.priority, PriorityLevel.URGENT)
        self.assertEqual(started.status, TicketStatus.PREPARING)

        # Verifica gravação do evento na auditoria
        self.assertEqual(logger.count(), 1)
        events = logger.fetch_all()
        self.assertEqual(events[0]["event_type"], "SERVICE_STARTED")
        self.assertEqual(events[0]["ticket_id"], "URG-1")
        self.assertEqual(events[0]["priority"], "URGENT")
        self.assertEqual(events[0]["queue_snapshot"], ["STD-1"])

        logger.close()

    def test_simulation_engine_full_lifecycle_with_sql_audit(self) -> None:
        """Simulação avança no tempo, conclui preparos e gera histórico SQL auditável."""
        queue = PriorityQueue()
        policy = QuotaFairnessPolicy()
        rules = BusinessRules()
        monitor = SlaMonitor(rules)
        logger = AuditLogger(db_path=":memory:")
        dispatcher = Dispatcher(queue, policy, monitor, logger)

        engine = SimulationEngine(dispatcher, queue, rules, logger)

        # 1. Chegada de pedido delivery simples (60s de preparo)
        order = Order(
            id="SIM-01",
            channel=OrderChannel.DELIVERY,
            complexity=OrderComplexity.SIMPLE,
            arrival_time=0,
            courier_waiting=True,
        )
        ticket = engine.enqueue(order)

        self.assertEqual(engine.current_time, 0)
        self.assertEqual(ticket.status, TicketStatus.WAITING)
        self.assertEqual(logger.count(), 1)  # ENQUEUED

        # 2. Avança 1 segundo: inicia preparo
        snap_1 = engine.advance(1)
        self.assertEqual(snap_1.current_time, 1)
        self.assertIsNotNone(snap_1.preparing_ticket)
        self.assertEqual(ticket.status, TicketStatus.PREPARING)
        self.assertEqual(logger.count(), 2)  # ENQUEUED + SERVICE_STARTED

        # 3. Avança até o segundo 60 (ainda em preparo: 1 + 60 = 61)
        snap_60 = engine.advance(59)
        self.assertEqual(snap_60.current_time, 60)
        self.assertIsNotNone(snap_60.preparing_ticket)
        self.assertEqual(ticket.status, TicketStatus.PREPARING)

        # 4. Avança para o segundo 61: preparo conclui
        snap_61 = engine.advance(1)
        self.assertEqual(snap_61.current_time, 61)
        self.assertIsNone(snap_61.preparing_ticket)
        self.assertEqual(ticket.status, TicketStatus.COMPLETED)
        self.assertEqual(logger.count(), 3)  # + PREPARATION_COMPLETED

        # 5. Exporta histórico SQL e valida integridade
        sql_export = logger.export_sql()
        self.assertIn("ENQUEUED", sql_export)
        self.assertIn("SERVICE_STARTED", sql_export)
        self.assertIn("PREPARATION_COMPLETED", sql_export)

        logger.close()


if __name__ == "__main__":
    unittest.main()
