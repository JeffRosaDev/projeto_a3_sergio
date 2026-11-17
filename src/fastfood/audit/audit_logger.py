"""Persistência SQLite transacional com ordem estável e histórico de intervenções."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from uuid import uuid4

from fastfood.domain.events import QueueEvent

DEFAULT_SCHEMA = """
-- KitchenFlow | Schema da auditoria | SQLite
-- O histórico é append-only: os triggers abaixo bloqueiam UPDATE e DELETE.

-- Um registro por mudança no estado de um pedido ou da fila.
CREATE TABLE IF NOT EXISTS queue_events (
    event_id            TEXT PRIMARY KEY, -- Identificador único do evento.
    ticket_id           TEXT NOT NULL, -- Identificador do pedido.
    event_type          TEXT NOT NULL, -- ENQUEUED, SERVICE_STARTED etc.
    simulated_second    INTEGER NOT NULL CHECK (simulated_second >= 0), -- Instante simulado.
    channel             TEXT NOT NULL, -- DELIVERY, PICKUP ou COUNTER.
    priority            TEXT NOT NULL, -- URGENT ou STANDARD.
    queue_size_before   INTEGER NOT NULL, -- Tamanho da fila antes do evento.
    queue_size_after    INTEGER NOT NULL, -- Tamanho da fila depois do evento.
    queue_snapshot      TEXT NOT NULL, -- IDs aguardando após o evento, em JSON.
    wait_seconds        INTEGER, -- Espera observada, quando aplicável.
    sla_target_seconds  INTEGER, -- Meta de espera do canal, em segundos.
    sla_status          TEXT, -- WAITING, AT_RISK, MET, BREACHED ou NULL.
    recorded_at         TEXT NOT NULL DEFAULT (datetime('now')) -- Data/hora UTC.
);

-- Um registro por comando, ajuste de regra ou incidente da simulação.
CREATE TABLE IF NOT EXISTS simulation_actions (
    action_id         TEXT PRIMARY KEY, -- Identificador único da ação.
    simulated_second  INTEGER NOT NULL, -- Instante simulado da ação.
    action            TEXT NOT NULL, -- Nome do comando/intervenção.
    details           TEXT NOT NULL, -- Parâmetros da ação em JSON.
    recorded_at       TEXT NOT NULL DEFAULT (datetime('now')) -- Data/hora UTC.
);

-- Numera eventos e ações juntos, na ordem em que foram gravados.
CREATE TABLE IF NOT EXISTS audit_sequence (
    sequence    INTEGER PRIMARY KEY AUTOINCREMENT, -- Ordem global da auditoria.
    entry_id    TEXT NOT NULL UNIQUE, -- ID presente na tabela do tipo indicado.
    entry_kind  TEXT NOT NULL -- event para fila; action para intervenção.
);

CREATE TRIGGER IF NOT EXISTS event_sequence
AFTER INSERT ON queue_events
BEGIN
    INSERT INTO audit_sequence (entry_id, entry_kind)
    VALUES (NEW.event_id, 'event');
END;

CREATE TRIGGER IF NOT EXISTS action_sequence
AFTER INSERT ON simulation_actions
BEGIN
    INSERT INTO audit_sequence (entry_id, entry_kind)
    VALUES (NEW.action_id, 'action');
END;
"""
# Triggers protegem contra alterações acidentais, inclusive SQL externo comum.
for _table in ("queue_events", "simulation_actions", "audit_sequence"):
    for _verb in ("UPDATE", "DELETE"):
        DEFAULT_SCHEMA += (
            f"\nCREATE TRIGGER IF NOT EXISTS {_table}_no_{_verb}\n"
            f"BEFORE {_verb} ON {_table}\n"
            "BEGIN\n"
            "    SELECT RAISE(ABORT, 'Historico append-only');\n"
            "END;\n"
        )

_OPERATION_LABELS = {
    "ENQUEUED": "Pedido entrou na fila",
    "SERVICE_STARTED": "Preparo iniciado",
    "PREPARATION_COMPLETED": "Preparo concluído",
    "CANCELLED": "Pedido cancelado",
    "CONFIG_INITIAL": "Configuração inicial",
    "CONFIG_CHANGED": "Configuração alterada",
    "BURST": "Lote de pedidos criado",
    "STATION_PAUSE": "Estação pausada",
    "STATION_RESUME": "Estação retomada",
    "PREPARATION_ADJUSTED": "Tempo de preparo ajustado",
    "PLAYBACK_STARTED": "Reprodução iniciada",
    "PLAYBACK_PAUSED": "Reprodução pausada",
    "TIME_ADVANCED": "Relógio avançado manualmente",
}
_CHANNEL_LABELS = {
    "DELIVERY": "Entrega",
    "PICKUP": "Retirada",
    "COUNTER": "Balcão",
}
_PRIORITY_LABELS = {"URGENT": "Urgente", "STANDARD": "Padrão"}
_SLA_LABELS = {
    "WAITING": "Aguardando",
    "AT_RISK": "Em risco",
    "MET": "Dentro da meta",
    "BREACHED": "Meta excedida",
}


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

    def timeline(self) -> list[dict]:
        """Reúne eventos e intervenções pela ordem global, sem inferir autoria pessoal."""
        with self._lock:
            rows = self._connection.execute("""
                SELECT s.sequence, s.entry_kind, s.entry_id,
                       COALESCE(e.simulated_second,a.simulated_second) AS simulated_second,
                       COALESCE(e.recorded_at,a.recorded_at) AS recorded_at,
                       COALESCE(e.event_type,a.action) AS operation,
                       e.ticket_id, e.channel, e.priority,
                       e.queue_size_before, e.queue_size_after,
                       e.queue_snapshot, e.wait_seconds, e.sla_target_seconds,
                       e.sla_status, a.details
                FROM audit_sequence s
                LEFT JOIN queue_events e ON s.entry_kind='event' AND s.entry_id=e.event_id
                LEFT JOIN simulation_actions a ON s.entry_kind='action' AND s.entry_id=a.action_id
                ORDER BY s.sequence
            """).fetchall()
            return [dict(row) for row in rows]

    def export_sql(self, output_path=None) -> str:
        """Exporta schema e dados com uma coluna por linha e ordem global preservada."""
        with self._lock:
            lines = [
                "-- KitchenFlow | Exportação completa da auditoria | SQLite",
                "-- Importe em um banco vazio. O schema cria as tabelas e protege o histórico.",
                "-- Cada bloco INSERT corresponde a um registro da trilha, em ordem global.",
                "",
                "-- SCHEMA: tabelas, sequenciamento automático e proteção append-only.",
                DEFAULT_SCHEMA.strip(),
                "",
                "-- DADOS: eventos e ações ordenados pela sequência original.",
                "BEGIN TRANSACTION;",
                "",
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
                operation = (
                    row["event_type"] if table == "queue_events" else row["action"]
                )
                record_type = "evento de fila" if table == "queue_events" else "ação"
                lines.append(
                    f"-- Registro de auditoria #{entry['sequence']:05d} "
                    f"| {record_type} | {operation}"
                )
                lines.append(self._format_insert(table, row))
                lines.append("")
            lines.append("COMMIT;")
            lines.append("")
            result = "\n".join(lines)
        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(result, encoding="utf-8")
        return result

    @staticmethod
    def _format_insert(table, row) -> str:
        """Mostra nomes das colunas e valores correspondentes em linhas separadas."""
        columns = list(row.keys())
        column_lines = ",\n".join(f"    {column}" for column in columns)
        value_lines = ",\n".join(
            f"    {AuditLogger._sql_quote(value)}" for value in row
        )
        return (
            f"INSERT INTO {table} (\n{column_lines}\n) VALUES (\n"
            f"{value_lines}\n);"
        )

    @staticmethod
    def _audit_record(row: dict) -> dict:
        """Converte a linha interna mista para um registro JSON tipado e explicado."""
        is_event = row["entry_kind"] == "event"
        record = {
            "sequencia": row["sequence"],
            "tipo_registro": "evento_de_fila" if is_event else "acao_de_simulacao",
            "id_registro": row["entry_id"],
            "segundo_simulado": row["simulated_second"],
            "registrado_em_utc": row["recorded_at"],
            "operacao": {
                "codigo": row["operation"],
                "descricao": _OPERATION_LABELS.get(
                    row["operation"], row["operation"]
                ),
            },
        }
        if is_event:
            snapshot = row["queue_snapshot"]
            record["pedido"] = {
                "id": row["ticket_id"],
                "canal": {
                    "codigo": row["channel"],
                    "descricao": _CHANNEL_LABELS.get(row["channel"], row["channel"]),
                },
                "prioridade": {
                    "codigo": row["priority"],
                    "descricao": _PRIORITY_LABELS.get(
                        row["priority"], row["priority"]
                    ),
                },
            }
            record["fila"] = {
                "tamanho_antes": row["queue_size_before"],
                "tamanho_depois": row["queue_size_after"],
                "pedidos_aguardando": (
                    json.loads(snapshot) if isinstance(snapshot, str) else snapshot
                ),
            }
            status = row["sla_status"]
            record["sla"] = {
                "espera_segundos": row["wait_seconds"],
                "meta_segundos": row["sla_target_seconds"],
                "resultado": (
                    {
                        "codigo": status,
                        "descricao": _SLA_LABELS.get(status, status),
                    }
                    if status
                    else None
                ),
            }
        else:
            details = row["details"]
            record["detalhes"] = (
                json.loads(details) if isinstance(details, str) else details
            )
        return record

    def export_json(self, rows=None, output_path=None, filters=None) -> str:
        """Exporta a trilha em JSON agrupado por evento ou acao, sem campos vazios."""
        if rows is None:
            rows = self.timeline()
        records = [self._audit_record(row) for row in rows]
        document = {
            "formato": "kitchenflow.audit.v1",
            "descricao": "Trilha de auditoria da simulação em ordem de registro.",
            "legenda": {
                "sequencia": "Ordem global em que evento ou ação foi gravado.",
                "tipo_registro": "Distingue evento_de_fila de acao_de_simulacao.",
                "segundo_simulado": "Instante do relógio interno da simulação, em segundos.",
                "registrado_em_utc": "Horário real de gravação, em UTC.",
                "pedidos_aguardando": "IDs na fila logo após o evento, na ordem de atendimento.",
                "sla.espera_segundos": "Null enquanto o pedido ainda não iniciou atendimento.",
                "sla.resultado": "Null quando o resultado de SLA ainda não se aplica.",
                "detalhes": "Parâmetros específicos do comando ou da alteração registrados.",
            },
            "filtros_aplicados": filters or {},
            "total_registros": len(records),
            "registros": records,
        }
        result = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
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
