"""Implementação do registrador de auditoria SQLite append-only."""

import json
from pathlib import Path
import sqlite3
from typing import Any

from fastfood.domain.events import QueueEvent


DEFAULT_SCHEMA = """
CREATE TABLE IF NOT EXISTS queue_events (
    event_id            TEXT    PRIMARY KEY,
    ticket_id           TEXT    NOT NULL,
    event_type          TEXT    NOT NULL,
    simulated_second    INTEGER NOT NULL,
    channel             TEXT    NOT NULL,
    priority            TEXT    NOT NULL,
    queue_size_before   INTEGER NOT NULL,
    queue_size_after    INTEGER NOT NULL,
    queue_snapshot      TEXT    NOT NULL,
    wait_seconds        INTEGER,
    sla_target_seconds  INTEGER,
    sla_status          TEXT,
    recorded_at         TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


class AuditLogger:
    """Registrador de eventos da simulação em SQLite com garantia append-only.

    Cada evento emitido pelo despachante ou motor de simulação é persistido
    de forma atômica (uma transação por evento) com snapshot em JSON da fila.
    Nenhuma operação de UPDATE ou DELETE é permitida, preservando a imutabilidade
    e a capacidade de reproduzir todo o histórico da simulação.
    """

    def __init__(
        self,
        db_path: str | Path = ":memory:",
        schema_path: str | Path | None = None,
    ) -> None:
        """Inicializa a conexão SQLite e garante a criação da tabela de auditoria.

        Args:
            db_path: Caminho do arquivo SQLite ou ':memory:' (padrão).
            schema_path: Caminho opcional para o arquivo schema.sql. Se omitido,
                         utiliza o arquivo em sql/schema.sql ou o schema padrão.
        """
        self._db_path = str(db_path)
        self._connection = sqlite3.connect(self._db_path)
        self._connection.row_factory = sqlite3.Row
        self._init_db(schema_path)

    def _init_db(self, schema_path: str | Path | None) -> None:
        """Cria as tabelas necessárias a partir do schema SQL."""
        sql = None
        if schema_path:
            path = Path(schema_path)
            if path.exists():
                sql = path.read_text(encoding="utf-8")
        else:
            default_path = Path(__file__).resolve().parents[3] / "sql" / "schema.sql"
            if default_path.exists():
                sql = default_path.read_text(encoding="utf-8")

        if not sql:
            sql = DEFAULT_SCHEMA

        with self._connection:
            self._connection.executescript(sql)

    def record(self, event: QueueEvent) -> None:
        """Registra um evento de fila de forma atômica no banco de dados.

        A gravação é append-only: apenas operações de INSERT são executadas.
        A transação garante que eventos parciais ou inválidos não corrompam
        o histórico de auditoria.

        Args:
            event: Objeto QueueEvent contendo todos os dados do fato operacional.
        """
        if not isinstance(event, QueueEvent):
            raise TypeError("event deve ser uma instância de QueueEvent.")

        snapshot_json = json.dumps(list(event.queue_snapshot), ensure_ascii=False)
        sla_status_val = event.sla_status.value if event.sla_status is not None else None

        sql = """
        INSERT INTO queue_events (
            event_id,
            ticket_id,
            event_type,
            simulated_second,
            channel,
            priority,
            queue_size_before,
            queue_size_after,
            queue_snapshot,
            wait_seconds,
            sla_target_seconds,
            sla_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._connection:
            self._connection.execute(
                sql,
                (
                    event.event_id,
                    event.ticket_id,
                    event.event_type.value,
                    event.simulated_second,
                    event.channel.value,
                    event.priority.value,
                    event.queue_size_before,
                    event.queue_size_after,
                    snapshot_json,
                    event.wait_seconds,
                    event.sla_target_seconds,
                    sla_status_val,
                ),
            )

    def export_sql(self, output_path: str | Path | None = None) -> str:
        """Exporta todo o histórico de eventos como um script SQL executável.

        O script gerado contém comandos INSERT executáveis protegidos por
        uma transação. Qualquer pessoa pode recriar o histórico executando o
        schema.sql e em seguida o script exportado.

        Args:
            output_path: Caminho de arquivo opcional onde o script será gravado.

        Returns:
            String contendo o script SQL executável.
        """
        cursor = self._connection.cursor()
        cursor.execute(
            """
            SELECT
                event_id,
                ticket_id,
                event_type,
                simulated_second,
                channel,
                priority,
                queue_size_before,
                queue_size_after,
                queue_snapshot,
                wait_seconds,
                sla_target_seconds,
                sla_status
            FROM queue_events
            ORDER BY rowid ASC
            """
        )
        rows = cursor.fetchall()

        lines: list[str] = [
            "-- =============================================================",
            "-- Exportação de auditoria da fila de prioridade para fast food",
            "-- Gerado automaticamente pelo AuditLogger (Etapa 6)",
            "-- =============================================================",
            "BEGIN TRANSACTION;",
        ]

        for row in rows:
            event_id = self._sql_quote(row["event_id"])
            ticket_id = self._sql_quote(row["ticket_id"])
            event_type = self._sql_quote(row["event_type"])
            simulated_second = str(row["simulated_second"])
            channel = self._sql_quote(row["channel"])
            priority = self._sql_quote(row["priority"])
            queue_size_before = str(row["queue_size_before"])
            queue_size_after = str(row["queue_size_after"])
            queue_snapshot = self._sql_quote(row["queue_snapshot"])
            wait_seconds = "NULL" if row["wait_seconds"] is None else str(row["wait_seconds"])
            sla_target_seconds = (
                "NULL" if row["sla_target_seconds"] is None else str(row["sla_target_seconds"])
            )
            sla_status = (
                "NULL" if row["sla_status"] is None else self._sql_quote(row["sla_status"])
            )

            stmt = (
                f"INSERT INTO queue_events ("
                f"event_id, ticket_id, event_type, simulated_second, channel, "
                f"priority, queue_size_before, queue_size_after, queue_snapshot, "
                f"wait_seconds, sla_target_seconds, sla_status"
                f") VALUES ("
                f"{event_id}, {ticket_id}, {event_type}, {simulated_second}, {channel}, "
                f"{priority}, {queue_size_before}, {queue_size_after}, {queue_snapshot}, "
                f"{wait_seconds}, {sla_target_seconds}, {sla_status}"
                f");"
            )
            lines.append(stmt)

        lines.append("COMMIT;")
        lines.append("")
        sql_content = "\n".join(lines)

        if output_path is not None:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(sql_content, encoding="utf-8")

        return sql_content

    def fetch_all(self) -> list[dict[str, Any]]:
        """Retorna todos os eventos registrados em formato de lista de dicionários.

        O campo queue_snapshot é desserializado de JSON para lista Python.
        """
        cursor = self._connection.cursor()
        cursor.execute(
            """
            SELECT
                event_id,
                ticket_id,
                event_type,
                simulated_second,
                channel,
                priority,
                queue_size_before,
                queue_size_after,
                queue_snapshot,
                wait_seconds,
                sla_target_seconds,
                sla_status,
                recorded_at
            FROM queue_events
            ORDER BY rowid ASC
            """
        )
        results = []
        for row in cursor.fetchall():
            row_dict = dict(row)
            try:
                row_dict["queue_snapshot"] = json.loads(row_dict["queue_snapshot"])
            except Exception:
                row_dict["queue_snapshot"] = []
            results.append(row_dict)
        return results

    def count(self) -> int:
        """Retorna a contagem total de eventos registrados."""
        cursor = self._connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM queue_events")
        return cursor.fetchone()[0]

    def close(self) -> None:
        """Fecha a conexão com o banco de dados SQLite."""
        self._connection.close()

    def __enter__(self) -> "AuditLogger":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    @staticmethod
    def _sql_quote(value: str) -> str:
        """Escapa texto para inclusão literal em comando SQL."""
        escaped = value.replace("'", "''")
        return f"'{escaped}'"
