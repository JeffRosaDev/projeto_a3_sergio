-- =============================================================
-- Schema da auditoria de eventos — fila de prioridade fast food
-- =============================================================
-- Execute este arquivo para criar o banco antes de importar
-- o histórico exportado em exports/logs.sql.
--
-- O registro é append-only: o aplicativo nunca executa UPDATE
-- nem DELETE sobre esta tabela, garantindo que o histórico
-- permaneça íntegro e auditável.
-- =============================================================

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
