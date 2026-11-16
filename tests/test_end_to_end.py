"""Testes de integração ponta a ponta e teste de estresse (Etapa 7)."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

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
from fastfood.queues.priority_policy import QuotaFairnessPolicy
from fastfood.queues.priority_queue import PriorityQueue
from fastfood.services.dispatcher import Dispatcher
from fastfood.services.simulation_engine import SimulationEngine
from fastfood.services.sla_monitor import SlaMonitor


class TestEndToEndAndStress(unittest.TestCase):
    """Valida o fluxo completo da simulação, cota anti-starvation, SLA e SQL."""

    def setUp(self) -> None:
        self.rules = BusinessRules()
        self.queue = PriorityQueue()
        self.policy = QuotaFairnessPolicy(self.rules)
        self.monitor = SlaMonitor(self.rules)
        self.logger = AuditLogger(db_path=":memory:")
        self.dispatcher = Dispatcher(self.queue, self.policy, self.monitor, self.logger)
        self.engine = SimulationEngine(
            self.dispatcher, self.queue, self.rules, self.logger
        )

    def tearDown(self) -> None:
        self.logger.close()

    def test_stress_fairness_quota_prevents_starvation_under_heavy_urgent_load(
        self,
    ) -> None:
        """Teste de estresse: 1 STANDARD contra 12 URGENT consecutivos.

        Comprova que:
        1. Nenhum pedido STANDARD sofre starvation (inicia após no máximo 3 URGENT).
        2. Pedidos que ultrapassam a meta de SLA têm BREACHED registrado.
        3. A estação nunca interrompe um preparo em andamento.
        """
        standard_order = Order(
            id="STD-STRESS",
            channel=OrderChannel.COUNTER,
            complexity=OrderComplexity.SIMPLE,
            arrival_time=0,
            courier_waiting=False,
        )
        standard_ticket = self.engine.enqueue(standard_order)

        urgent_tickets = []
        for idx in range(1, 13):
            urg_order = Order(
                id=f"URG-{idx:02d}",
                channel=OrderChannel.DELIVERY,
                complexity=OrderComplexity.SIMPLE,
                arrival_time=0,
                courier_waiting=True,
            )
            urgent_tickets.append(self.engine.enqueue(urg_order))

        # Avança 1s -> despacha URG-01 (1º urgente, termina em t=61)
        self.engine.advance(1)
        self.assertEqual(self.engine.preparing_ticket.id, "URG-01")

        # Avança 60s (t=61) -> conclui URG-01 e despacha URG-02 (2º urgente)
        self.engine.advance(60)
        self.assertEqual(self.engine.preparing_ticket.id, "URG-02")

        # Avança 60s (t=121) -> conclui URG-02 e despacha URG-03 (3º urgente)
        self.engine.advance(60)
        self.assertEqual(self.engine.preparing_ticket.id, "URG-03")

        # Avança 60s (t=181) -> conclui URG-03; cota de 3 atingida -> STD-STRESS!
        self.engine.advance(60)
        self.assertEqual(self.engine.preparing_ticket.id, "STD-STRESS")
        self.assertEqual(standard_ticket.status, TicketStatus.PREPARING)
        self.assertEqual(standard_ticket.started_at, 181)

        # Espera de STD-STRESS foi 181s <= 480s (meta COUNTER) -> SLA MET
        self.assertEqual(
            self.monitor.status(standard_ticket, self.engine.current_time),
            SlaStatus.MET,
        )

        # Avança até esvaziar toda a fila (9 urgentes * 60s + 60s do STD)
        self.engine.advance(600)
        self.assertIsNone(self.engine.preparing_ticket)
        self.assertEqual(self.engine.advance(0).queue_snapshot, [])

        # Verifica ordem exata de início na auditoria SQL
        started_events = [
            e
            for e in self.logger.fetch_all()
            if e["event_type"] == QueueEventType.SERVICE_STARTED.value
        ]
        started_ids = [e["ticket_id"] for e in started_events]
        self.assertEqual(started_ids[:4], ["URG-01", "URG-02", "URG-03", "STD-STRESS"])

        # Os últimos urgentes esperaram mais de 180s -> SLA BREACHED registrado
        late_urgent = next(e for e in started_events if e["ticket_id"] == "URG-12")
        self.assertGreater(late_urgent["wait_seconds"], 180)
        self.assertEqual(late_urgent["sla_status"], SlaStatus.BREACHED.value)

    def test_full_end_to_end_flow_and_executable_sql_reproduction(self) -> None:
        """Fluxo completo com chegadas dinâmicas durante preparo e restauração SQL."""
        # t=0: chega pedido balcão médio (120s preparo)
        o1 = Order("ORD-01", OrderChannel.COUNTER, OrderComplexity.MEDIUM, 0, False)
        self.engine.enqueue(o1)

        # t=1: ORD-01 inicia preparo (termina em t=121)
        self.engine.advance(1)
        self.assertEqual(self.engine.preparing_ticket.id, "ORD-01")

        # t=50: durante o preparo de ORD-01, chegam um PICKUP e um DELIVERY urgente
        self.engine.advance(49)  # Chegada real no relógio da simulação.
        o2 = Order("ORD-02", OrderChannel.PICKUP, OrderComplexity.SIMPLE, 50, False)
        o3 = Order("ORD-03", OrderChannel.DELIVERY, OrderComplexity.SIMPLE, 50, True)
        self.engine.enqueue(o2)
        self.engine.enqueue(o3)

        # Avança até t=121: ORD-01 conclui e ORD-03 (URGENT) fura a fila
        self.engine.advance(71)
        self.assertEqual(self.engine.current_time, 121)
        self.assertEqual(self.engine.preparing_ticket.id, "ORD-03")
        self.assertEqual(self.engine.preparing_ticket.priority, PriorityLevel.URGENT)

        # Avança até t=250: conclui ORD-03 (t=181) e ORD-02 (t=241)
        self.engine.advance(129)
        self.assertIsNone(self.engine.preparing_ticket)
        self.assertEqual(self.logger.count(), 9)  # 3 pedidos * 3 eventos cada

        # Exporta SQL e reproduz o histórico em um banco SQLite limpo via schema.sql
        with tempfile.TemporaryDirectory() as tmpdir:
            exported_path = Path(tmpdir) / "logs.sql"
            sql_text = self.logger.export_sql(output_path=exported_path)
            self.assertTrue(exported_path.exists())

            schema_path = Path(__file__).resolve().parents[1] / "sql" / "schema.sql"
            verify_conn = sqlite3.connect(":memory:")
            verify_conn.row_factory = sqlite3.Row
            verify_conn.executescript(schema_path.read_text(encoding="utf-8"))
            verify_conn.executescript(sql_text)

            rows = verify_conn.execute(
                "SELECT * FROM queue_events ORDER BY rowid ASC"
            ).fetchall()
            self.assertEqual(len(rows), 9)
            self.assertEqual(
                [r["event_type"] for r in rows[:4]],
                ["ENQUEUED", "SERVICE_STARTED", "ENQUEUED", "ENQUEUED"],
            )
            self.assertEqual(json.loads(rows[0]["queue_snapshot"]), ["ORD-01"])
            verify_conn.close()


if __name__ == "__main__":
    unittest.main()
