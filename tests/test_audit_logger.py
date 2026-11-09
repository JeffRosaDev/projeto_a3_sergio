"""Testes da camada de auditoria SQL (Etapa 6)."""

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from fastfood.audit.audit_logger import AuditLogger
from fastfood.domain.enums import (
    OrderChannel,
    PriorityLevel,
    QueueEventType,
    SlaStatus,
)
from fastfood.domain.events import QueueEvent


class TestAuditLogger(unittest.TestCase):
    """Garante o cumprimento dos requisitos de auditoria SQL da Etapa 6."""

    def setUp(self) -> None:
        self.logger = AuditLogger(db_path=":memory:")

    def tearDown(self) -> None:
        self.logger.close()

    def test_record_enqueued_event(self) -> None:
        """Grava evento de entrada na fila com snapshot e contagens."""
        event = QueueEvent(
            event_id="evt-01",
            ticket_id="ord-101",
            event_type=QueueEventType.ENQUEUED,
            simulated_second=10,
            channel=OrderChannel.DELIVERY,
            priority=PriorityLevel.URGENT,
            queue_size_before=0,
            queue_size_after=1,
            queue_snapshot=("ord-101",),
            sla_target_seconds=180,
        )

        self.logger.record(event)
        self.assertEqual(self.logger.count(), 1)

        events = self.logger.fetch_all()
        self.assertEqual(len(events), 1)
        row = events[0]

        self.assertEqual(row["event_id"], "evt-01")
        self.assertEqual(row["ticket_id"], "ord-101")
        self.assertEqual(row["event_type"], "ENQUEUED")
        self.assertEqual(row["simulated_second"], 10)
        self.assertEqual(row["channel"], "DELIVERY")
        self.assertEqual(row["priority"], "URGENT")
        self.assertEqual(row["queue_size_before"], 0)
        self.assertEqual(row["queue_size_after"], 1)
        self.assertEqual(row["queue_snapshot"], ["ord-101"])
        self.assertIsNone(row["wait_seconds"])
        self.assertEqual(row["sla_target_seconds"], 180)
        self.assertIsNone(row["sla_status"])
        self.assertIsNotNone(row["recorded_at"])

    def test_record_service_started_event(self) -> None:
        """Grava evento de início de preparo com métricas de SLA e espera."""
        event = QueueEvent(
            event_id="evt-02",
            ticket_id="ord-101",
            event_type=QueueEventType.SERVICE_STARTED,
            simulated_second=35,
            channel=OrderChannel.DELIVERY,
            priority=PriorityLevel.URGENT,
            queue_size_before=1,
            queue_size_after=0,
            queue_snapshot=(),
            wait_seconds=25,
            sla_target_seconds=180,
            sla_status=SlaStatus.MET,
        )

        self.logger.record(event)
        self.assertEqual(self.logger.count(), 1)

        events = self.logger.fetch_all()
        row = events[0]
        self.assertEqual(row["event_type"], "SERVICE_STARTED")
        self.assertEqual(row["wait_seconds"], 25)
        self.assertEqual(row["sla_status"], "MET")
        self.assertEqual(row["queue_snapshot"], [])

    def test_record_rejects_invalid_type(self) -> None:
        """Garante que apenas objetos QueueEvent são aceitos."""
        with self.assertRaises(TypeError):
            self.logger.record("evento invalido")  # type: ignore[arg-type]

    def test_transaction_atomicity_on_duplicate_id(self) -> None:
        """A chave primária protege contra IDs duplicados e faz rollback da transação."""
        event1 = QueueEvent(
            event_id="evt-same",
            ticket_id="ord-1",
            event_type=QueueEventType.ENQUEUED,
            simulated_second=0,
            channel=OrderChannel.COUNTER,
            priority=PriorityLevel.STANDARD,
            queue_size_before=0,
            queue_size_after=1,
            queue_snapshot=("ord-1",),
        )
        self.logger.record(event1)
        self.assertEqual(self.logger.count(), 1)

        # Tentativa de gravar evento com mesmo event_id deve falhar
        event2 = QueueEvent(
            event_id="evt-same",
            ticket_id="ord-2",
            event_type=QueueEventType.ENQUEUED,
            simulated_second=5,
            channel=OrderChannel.PICKUP,
            priority=PriorityLevel.STANDARD,
            queue_size_before=1,
            queue_size_after=2,
            queue_snapshot=("ord-1", "ord-2"),
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.logger.record(event2)

        # O estado permanece integro com 1 evento
        self.assertEqual(self.logger.count(), 1)

    def test_export_sql_is_executable_and_reproducible(self) -> None:
        """Critério de aceite da Etapa 6:

        Iniciar um novo banco pelo schema.sql, executar o SQL exportado
        e recuperar fielmente toda a sequência de eventos sem perdas.
        """
        e1 = QueueEvent(
            event_id="evt-export-1",
            ticket_id="ord-A",
            event_type=QueueEventType.ENQUEUED,
            simulated_second=0,
            channel=OrderChannel.DELIVERY,
            priority=PriorityLevel.URGENT,
            queue_size_before=0,
            queue_size_after=1,
            queue_snapshot=("ord-A",),
            sla_target_seconds=180,
        )
        e2 = QueueEvent(
            event_id="evt-export-2",
            ticket_id="ord-B",
            event_type=QueueEventType.ENQUEUED,
            simulated_second=10,
            channel=OrderChannel.COUNTER,
            priority=PriorityLevel.STANDARD,
            queue_size_before=1,
            queue_size_after=2,
            queue_snapshot=("ord-A", "ord-B"),
            sla_target_seconds=480,
        )
        e3 = QueueEvent(
            event_id="evt-export-3",
            ticket_id="ord-A",
            event_type=QueueEventType.SERVICE_STARTED,
            simulated_second=20,
            channel=OrderChannel.DELIVERY,
            priority=PriorityLevel.URGENT,
            queue_size_before=2,
            queue_size_after=1,
            queue_snapshot=("ord-B",),
            wait_seconds=20,
            sla_target_seconds=180,
            sla_status=SlaStatus.MET,
        )

        self.logger.record(e1)
        self.logger.record(e2)
        self.logger.record(e3)

        with tempfile.TemporaryDirectory() as tmpdir:
            sql_file = Path(tmpdir) / "exported_test.sql"
            exported_sql = self.logger.export_sql(output_path=sql_file)

            self.assertTrue(sql_file.exists())
            self.assertIn("BEGIN TRANSACTION;", exported_sql)
            self.assertIn("COMMIT;", exported_sql)
            self.assertIn("INSERT INTO queue_events", exported_sql)

            # Novo banco isolado para reproduzir o histórico
            new_conn = sqlite3.connect(":memory:")
            new_conn.row_factory = sqlite3.Row

            # Aplica o schema.sql
            schema_file = Path(__file__).resolve().parents[1] / "sql" / "schema.sql"
            new_conn.executescript(schema_file.read_text(encoding="utf-8"))

            # Executa o SQL exportado
            new_conn.executescript(exported_sql)

            # Verifica se os 3 eventos foram reconstituídos perfeitamente
            cur = new_conn.cursor()
            cur.execute("SELECT * FROM queue_events ORDER BY rowid ASC")
            rows = cur.fetchall()

            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[0]["event_id"], "evt-export-1")
            self.assertEqual(rows[1]["event_id"], "evt-export-2")
            self.assertEqual(rows[2]["event_id"], "evt-export-3")
            self.assertEqual(rows[2]["wait_seconds"], 20)
            self.assertEqual(rows[2]["sla_status"], "MET")
            self.assertEqual(json.loads(rows[2]["queue_snapshot"]), ["ord-B"])

            new_conn.close()


if __name__ == "__main__":
    unittest.main()
