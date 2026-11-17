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

CREATE TRIGGER IF NOT EXISTS queue_events_no_UPDATE
BEFORE UPDATE ON queue_events
BEGIN
    SELECT RAISE(ABORT, 'Historico append-only');
END;

CREATE TRIGGER IF NOT EXISTS queue_events_no_DELETE
BEFORE DELETE ON queue_events
BEGIN
    SELECT RAISE(ABORT, 'Historico append-only');
END;

CREATE TRIGGER IF NOT EXISTS simulation_actions_no_UPDATE
BEFORE UPDATE ON simulation_actions
BEGIN
    SELECT RAISE(ABORT, 'Historico append-only');
END;

CREATE TRIGGER IF NOT EXISTS simulation_actions_no_DELETE
BEFORE DELETE ON simulation_actions
BEGIN
    SELECT RAISE(ABORT, 'Historico append-only');
END;

CREATE TRIGGER IF NOT EXISTS audit_sequence_no_UPDATE
BEFORE UPDATE ON audit_sequence
BEGIN
    SELECT RAISE(ABORT, 'Historico append-only');
END;

CREATE TRIGGER IF NOT EXISTS audit_sequence_no_DELETE
BEFORE DELETE ON audit_sequence
BEGIN
    SELECT RAISE(ABORT, 'Historico append-only');
END;
