"""Persistência SQLite transacional com ordem estável e histórico de intervenções."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from uuid import uuid4

from fastfood.domain.events import QueueEvent

DEFAULT_SCHEMA = """
CREATE TABLE IF NOT EXISTS queue_events (
 event_id TEXT PRIMARY KEY, ticket_id TEXT NOT NULL, event_type TEXT NOT NULL,
 simulated_second INTEGER NOT NULL CHECK(simulated_second >= 0),
 channel TEXT NOT NULL, priority TEXT NOT NULL,
 queue_size_before INTEGER NOT NULL, queue_size_after INTEGER NOT NULL,
 queue_snapshot TEXT NOT NULL, wait_seconds INTEGER, sla_target_seconds INTEGER,
 sla_status TEXT, recorded_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS simulation_actions (
 action_id TEXT PRIMARY KEY, simulated_second INTEGER NOT NULL,
 action TEXT NOT NULL, details TEXT NOT NULL,
 recorded_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS audit_sequence (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT,
 entry_id TEXT NOT NULL UNIQUE, entry_kind TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS event_sequence AFTER INSERT ON queue_events
 BEGIN INSERT INTO audit_sequence(entry_id,entry_kind) VALUES(NEW.event_id,'event'); END;
CREATE TRIGGER IF NOT EXISTS action_sequence AFTER INSERT ON simulation_actions
 BEGIN INSERT INTO audit_sequence(entry_id,entry_kind) VALUES(NEW.action_id,'action'); END;
"""
# Triggers protegem contra alterações acidentais, inclusive SQL externo comum.
for _table in ("queue_events", "simulation_actions", "audit_sequence"):
    for _verb in ("UPDATE", "DELETE"):
        DEFAULT_SCHEMA += f"CREATE TRIGGER IF NOT EXISTS {_table}_no_{_verb} BEFORE {_verb} ON {_table} BEGIN SELECT RAISE(ABORT, 'Historico append-only'); END;\n"


class AuditLogger:
    """Conexão por sessão, compartilhável entre reruns e serializada por RLock."""

    def __init__(self, db_path=":memory:", schema_path=None):
        """Cria o schema; arquivos opcionais tornam o histórico durável em disco."""
        self._lock = RLock()  # Serializa transações da mesma sessão.
        self._connection = sqlite3.connect(str(db_path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        schema = (
            Path(schema_path).read_text(encoding="utf-8")
            if schema_path
            else DEFAULT_SCHEMA
        )
        self._connection.executescript(schema)

    @contextmanager
    def transaction(self):
        """Savepoint aninhável: confirma tudo ou desfaz a operação inteira."""
        with self._lock:
            name = "s" + uuid4().hex
            self._connection.execute(f"SAVEPOINT {name}")
            try:
                yield
                self._connection.execute(f"RELEASE {name}")
            except BaseException:
                self._connection.execute(f"ROLLBACK TO {name}")
                self._connection.execute(f"RELEASE {name}")
                raise

    def record(self, event: QueueEvent) -> None:
        """Insere um evento validado; parâmetros SQL impedem injeção por IDs."""
        if not isinstance(event, QueueEvent):
            raise TypeError("event deve ser QueueEvent.")
        with self.transaction():
            self._connection.execute(
                """INSERT INTO queue_events
              (event_id,ticket_id,event_type,simulated_second,channel,priority,
               queue_size_before,queue_size_after,queue_snapshot,wait_seconds,sla_target_seconds,sla_status)
              VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    event.event_id,
                    event.ticket_id,
                    event.event_type.value,
                    event.simulated_second,
                    event.channel.value,
                    event.priority.value,
                    event.queue_size_before,
                    event.queue_size_after,
                    json.dumps(event.queue_snapshot, ensure_ascii=False),
                    event.wait_seconds,
                    event.sla_target_seconds,
                    event.sla_status.value if event.sla_status else None,
                ),
            )

    def record_action(self, now: int, action: str, details: dict) -> None:
        """Registra configuração ou incidente, com instante e parâmetros completos."""
        with self.transaction():
            self._connection.execute(
                "INSERT INTO simulation_actions(action_id,simulated_second,action,details) VALUES(?,?,?,?)",
                (uuid4().hex, now, action, json.dumps(details, ensure_ascii=False)),
            )

    def fetch_all(self) -> list[dict]:
        """Lê eventos em ordem de inserção, inclusive no mesmo segundo."""
        with self._lock:
            rows = [
                dict(r)
                for r in self._connection.execute(
                    "SELECT * FROM queue_events ORDER BY rowid"
                )
            ]
        for row in rows:
            row["queue_snapshot"] = json.loads(row["queue_snapshot"])
        return rows

    def actions(self) -> list[dict]:
        """Consulta intervenções e configurações sem alterar registros."""
        with self._lock:
            return [
                dict(r)
                for r in self._connection.execute(
                    "SELECT * FROM simulation_actions ORDER BY rowid"
                )
            ]

    def count(self) -> int:
        """Conta eventos operacionais; ações ficam em tabela própria."""
        with self._lock:
            return self._connection.execute(
                "SELECT COUNT(*) FROM queue_events"
            ).fetchone()[0]

    def export_sql(self, output_path=None) -> str:
        """Exporta schema e dados em ordem global, preservando recorded_at e a sequência."""
        with self._lock:
            lines = [
                "-- KitchenFlow: importar em banco vazio.",
                DEFAULT_SCHEMA,
                "BEGIN TRANSACTION;",
            ]
            for entry in self._connection.execute(
                "SELECT * FROM audit_sequence ORDER BY sequence"
            ).fetchall():
                table, key = (
                    ("queue_events", "event_id")
                    if entry["entry_kind"] == "event"
                    else ("simulation_actions", "action_id")
                )
                row = self._connection.execute(
                    f"SELECT * FROM {table} WHERE {key}=?", (entry["entry_id"],)
                ).fetchone()
                values = ",".join(self._sql_quote(v) for v in row)
                lines.append(
                    f"INSERT INTO {table} ({','.join(row.keys())}) VALUES ({values});"
                )
            lines.append("COMMIT;")
            result = "\n".join(lines)
        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(result, encoding="utf-8")
        return result

    @staticmethod
    def _sql_quote(value):
        """Codifica literais na exportação; não é usada para executar entradas."""
        if value is None:
            return "NULL"
        if isinstance(value, (int, float)):
            return str(value)
        return "'" + value.replace("'", "''") + "'"

    def close(self):
        """Libera a conexão da sessão."""
        with self._lock:
            self._connection.close()

    def __enter__(self):
        """Permite uso com with para fechamento garantido."""
        return self

    def __exit__(self, *args):
        """Fecha ao sair do contexto."""
        self.close()
