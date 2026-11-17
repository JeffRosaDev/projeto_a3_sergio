-- KitchenFlow | Exportação completa da auditoria | SQLite
-- Importe em um banco vazio. O schema cria as tabelas e protege o histórico.
-- Cada bloco INSERT corresponde a um registro da trilha, em ordem global.

-- SCHEMA: tabelas, sequenciamento automático e proteção append-only.
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

-- DADOS: eventos e ações ordenados pela sequência original.
BEGIN TRANSACTION;

-- Registro de auditoria #00001 | ação | CONFIG_INITIAL
INSERT INTO simulation_actions (
    action_id,
    simulated_second,
    action,
    details,
    recorded_at
) VALUES (
    'c899fc65041c4584815531f246193601',
    0,
    'CONFIG_INITIAL',
    '{"sla": {"DELIVERY": 180, "PICKUP": 300, "COUNTER": 480}, "preparo": {"SIMPLE": 60, "MEDIUM": 120, "COMPLEX": 180}, "cota": 3, "risco": 0.8, "delivery_urgente": true}',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00002 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    '881dcaef-e210-4aa3-ab12-a6ba6f4b53ee',
    'PED-0001',
    'ENQUEUED',
    0,
    'COUNTER',
    'STANDARD',
    0,
    1,
    '["PED-0001"]',
    NULL,
    480,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00003 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    'dfedf35b-137a-4f2b-8b4e-193be0cc6c6c',
    'PED-0002',
    'ENQUEUED',
    0,
    'PICKUP',
    'STANDARD',
    1,
    2,
    '["PED-0001", "PED-0002"]',
    NULL,
    300,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00004 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    '5139dcc6-8faa-4da2-b099-a6b80fc91a61',
    'PED-0003',
    'ENQUEUED',
    0,
    'DELIVERY',
    'URGENT',
    2,
    3,
    '["PED-0003", "PED-0001", "PED-0002"]',
    NULL,
    180,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00005 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    'e84b33fa-242d-4a3a-b064-bc567c9a983f',
    'PED-0004',
    'ENQUEUED',
    0,
    'COUNTER',
    'STANDARD',
    3,
    4,
    '["PED-0003", "PED-0001", "PED-0002", "PED-0004"]',
    NULL,
    480,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00006 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    '27d9f93b-a7d2-43d1-b8d7-cc3736b1f17e',
    'PED-0005',
    'ENQUEUED',
    0,
    'COUNTER',
    'STANDARD',
    4,
    5,
    '["PED-0003", "PED-0001", "PED-0002", "PED-0004", "PED-0005"]',
    NULL,
    480,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00007 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    'bf714ad5-4906-4081-8621-12b942a07655',
    'PED-0006',
    'ENQUEUED',
    0,
    'DELIVERY',
    'URGENT',
    5,
    6,
    '["PED-0003", "PED-0006", "PED-0001", "PED-0002", "PED-0004", "PED-0005"]',
    NULL,
    180,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00008 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    'e442ecbd-649b-4930-a05d-80237377254c',
    'PED-0007',
    'ENQUEUED',
    0,
    'DELIVERY',
    'URGENT',
    6,
    7,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0001", "PED-0002", "PED-0004", "PED-0005"]',
    NULL,
    180,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00009 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    'baf53e51-cd65-4214-be9b-58bfbecd07d0',
    'PED-0008',
    'ENQUEUED',
    0,
    'DELIVERY',
    'URGENT',
    7,
    8,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0001", "PED-0002", "PED-0004", "PED-0005"]',
    NULL,
    180,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00010 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    '54a7f63b-7cae-4f01-a926-92d0cb95585e',
    'PED-0009',
    'ENQUEUED',
    0,
    'COUNTER',
    'STANDARD',
    8,
    9,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009"]',
    NULL,
    480,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00011 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    'bd6146f2-d540-441f-b3f1-2cdc21a95953',
    'PED-0010',
    'ENQUEUED',
    0,
    'DELIVERY',
    'URGENT',
    9,
    10,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009"]',
    NULL,
    180,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00012 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    '17d05d29-b06a-4ef2-9b79-bf6e00e7ee9b',
    'PED-0011',
    'ENQUEUED',
    0,
    'PICKUP',
    'STANDARD',
    10,
    11,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011"]',
    NULL,
    300,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00013 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    '526ecff9-3d08-4835-9efe-901b773bc27e',
    'PED-0012',
    'ENQUEUED',
    0,
    'DELIVERY',
    'URGENT',
    11,
    12,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011"]',
    NULL,
    180,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00014 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    'db5e6b93-da74-46e2-9510-143cba869c14',
    'PED-0013',
    'ENQUEUED',
    0,
    'DELIVERY',
    'URGENT',
    12,
    13,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011"]',
    NULL,
    180,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00015 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    '93e3d576-e53f-4087-b168-4be774c2dc57',
    'PED-0014',
    'ENQUEUED',
    0,
    'COUNTER',
    'STANDARD',
    13,
    14,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014"]',
    NULL,
    480,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00016 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    '0f68eba1-7a64-4d29-a9aa-295981efdd24',
    'PED-0015',
    'ENQUEUED',
    0,
    'DELIVERY',
    'URGENT',
    14,
    15,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014"]',
    NULL,
    180,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00017 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    '00ee94f9-f063-4f93-abbd-f80a904acd31',
    'PED-0016',
    'ENQUEUED',
    0,
    'DELIVERY',
    'URGENT',
    15,
    16,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014"]',
    NULL,
    180,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00018 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    'e15ae9d0-775f-4931-a59d-db9d2d2d20e6',
    'PED-0017',
    'ENQUEUED',
    0,
    'DELIVERY',
    'URGENT',
    16,
    17,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014"]',
    NULL,
    180,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00019 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    'ec5b8edc-e67b-4a55-a840-e577bd9c73cc',
    'PED-0018',
    'ENQUEUED',
    0,
    'DELIVERY',
    'URGENT',
    17,
    18,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014"]',
    NULL,
    180,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00020 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    '969a8099-7227-4dbc-8690-3b92585d1b35',
    'PED-0019',
    'ENQUEUED',
    0,
    'DELIVERY',
    'URGENT',
    18,
    19,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014"]',
    NULL,
    180,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00021 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    '57a3eb1d-1670-4bcb-a12f-c0153cbb5ac8',
    'PED-0020',
    'ENQUEUED',
    0,
    'DELIVERY',
    'URGENT',
    19,
    20,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014"]',
    NULL,
    180,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00022 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    '6af7627f-beed-40b5-8d5e-f9be865ff3b7',
    'PED-0021',
    'ENQUEUED',
    0,
    'PICKUP',
    'STANDARD',
    20,
    21,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021"]',
    NULL,
    300,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00023 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    'e3c17f38-5bf8-47fe-ae1d-b5eb10c3e8e5',
    'PED-0022',
    'ENQUEUED',
    0,
    'PICKUP',
    'STANDARD',
    21,
    22,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022"]',
    NULL,
    300,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00024 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    'a8ae3e26-d789-4982-81e6-913c4f0e9922',
    'PED-0023',
    'ENQUEUED',
    0,
    'DELIVERY',
    'URGENT',
    22,
    23,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022"]',
    NULL,
    180,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00025 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    '837f994b-d9ca-4938-b4d0-93dba3ed6251',
    'PED-0024',
    'ENQUEUED',
    0,
    'DELIVERY',
    'URGENT',
    23,
    24,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022"]',
    NULL,
    180,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00026 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    '5bd7f078-a6d8-4739-815c-89f92edd58cd',
    'PED-0025',
    'ENQUEUED',
    0,
    'DELIVERY',
    'URGENT',
    24,
    25,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022"]',
    NULL,
    180,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00027 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    '8c3591f8-3f8c-4d7e-8cc4-9baaa3d87066',
    'PED-0026',
    'ENQUEUED',
    0,
    'PICKUP',
    'STANDARD',
    25,
    26,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026"]',
    NULL,
    300,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00028 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    '7d51faf4-83ac-46d9-92e0-4e0e03705223',
    'PED-0027',
    'ENQUEUED',
    0,
    'DELIVERY',
    'URGENT',
    26,
    27,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026"]',
    NULL,
    180,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00029 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    '9469a2cb-c9fd-4dd4-b0a6-3e5951f5c8b4',
    'PED-0028',
    'ENQUEUED',
    0,
    'DELIVERY',
    'URGENT',
    27,
    28,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026"]',
    NULL,
    180,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00030 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    '60efc53c-65bc-4df6-98ae-5ae0fe77a11b',
    'PED-0029',
    'ENQUEUED',
    0,
    'COUNTER',
    'STANDARD',
    28,
    29,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029"]',
    NULL,
    480,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00031 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    '698b5ba8-f7fb-45d0-9ece-2e3c45690453',
    'PED-0030',
    'ENQUEUED',
    0,
    'DELIVERY',
    'URGENT',
    29,
    30,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029"]',
    NULL,
    180,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00032 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    'bf58bc1a-984d-48af-81ce-aac50b326171',
    'PED-0031',
    'ENQUEUED',
    0,
    'DELIVERY',
    'URGENT',
    30,
    31,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029"]',
    NULL,
    180,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00033 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    'f4f88d1f-baca-44e4-8fe7-f90e2c8de7fb',
    'PED-0032',
    'ENQUEUED',
    0,
    'DELIVERY',
    'URGENT',
    31,
    32,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029"]',
    NULL,
    180,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00034 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    '4f296e06-7391-4e11-a522-7ef6de817eb0',
    'PED-0033',
    'ENQUEUED',
    0,
    'PICKUP',
    'STANDARD',
    32,
    33,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033"]',
    NULL,
    300,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00035 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    '9194ca35-7749-4ca8-959d-d488b2fd81e5',
    'PED-0034',
    'ENQUEUED',
    0,
    'DELIVERY',
    'URGENT',
    33,
    34,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033"]',
    NULL,
    180,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00036 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    'ccf21bc0-a6a9-42bc-8b27-76bc3af3390e',
    'PED-0035',
    'ENQUEUED',
    0,
    'DELIVERY',
    'URGENT',
    34,
    35,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033"]',
    NULL,
    180,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00037 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    'eb60957e-d300-4cf3-a590-c93f0ee2dad3',
    'PED-0036',
    'ENQUEUED',
    0,
    'DELIVERY',
    'URGENT',
    35,
    36,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033"]',
    NULL,
    180,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00038 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    'cd2bfb5f-fd6a-47e6-abed-fd85993f90e1',
    'PED-0037',
    'ENQUEUED',
    0,
    'COUNTER',
    'STANDARD',
    36,
    37,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037"]',
    NULL,
    480,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00039 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    '6fce2542-7955-4ce6-9a4b-c8c3b3ce05a0',
    'PED-0038',
    'ENQUEUED',
    0,
    'COUNTER',
    'STANDARD',
    37,
    38,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038"]',
    NULL,
    480,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00040 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    '11723f6c-c3ee-4c75-a385-e5d69cd0c40b',
    'PED-0039',
    'ENQUEUED',
    0,
    'COUNTER',
    'STANDARD',
    38,
    39,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    NULL,
    480,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00041 | evento de fila | ENQUEUED
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
    sla_status,
    recorded_at
) VALUES (
    'fa1fce51-460a-474b-8197-a0fb56e4bdc3',
    'PED-0040',
    'ENQUEUED',
    0,
    'DELIVERY',
    'URGENT',
    39,
    40,
    '["PED-0003", "PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    NULL,
    180,
    NULL,
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00042 | ação | BURST
INSERT INTO simulation_actions (
    action_id,
    simulated_second,
    action,
    details,
    recorded_at
) VALUES (
    '02faf71b370d4d69bd62947fbae0efc6',
    0,
    'BURST',
    '{"count": 40, "seed": 42, "urgent_percent": 60, "scenario": "Aleatório"}',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00043 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    '8c6104fe-a1fe-470d-9463-31a9827116cc',
    'PED-0003',
    'SERVICE_STARTED',
    1,
    'DELIVERY',
    'URGENT',
    40,
    39,
    '["PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    1,
    180,
    'MET',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00044 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    '792ca58c-af63-4f4d-ae85-c85a8d540a79',
    'PED-0003',
    'PREPARATION_COMPLETED',
    61,
    'DELIVERY',
    'URGENT',
    39,
    39,
    '["PED-0006", "PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    1,
    180,
    'MET',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00045 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    '4677c4ba-3ae9-4ab6-b41b-e67515dab544',
    'PED-0006',
    'SERVICE_STARTED',
    61,
    'DELIVERY',
    'URGENT',
    39,
    38,
    '["PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    61,
    180,
    'MET',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00046 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    'd64da48d-720f-4f27-89c3-1129ed85bb48',
    'PED-0006',
    'PREPARATION_COMPLETED',
    121,
    'DELIVERY',
    'URGENT',
    38,
    38,
    '["PED-0007", "PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    61,
    180,
    'MET',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00047 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    '46a97950-5694-49bf-9c02-8c3772cf5e8a',
    'PED-0007',
    'SERVICE_STARTED',
    121,
    'DELIVERY',
    'URGENT',
    38,
    37,
    '["PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    121,
    180,
    'MET',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00048 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    '65aa468b-cf80-47c4-8d25-8e295907790b',
    'PED-0007',
    'PREPARATION_COMPLETED',
    181,
    'DELIVERY',
    'URGENT',
    37,
    37,
    '["PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0001", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    121,
    180,
    'MET',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00049 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    '338b7a03-f69d-4423-9b7f-122481ce5f4d',
    'PED-0001',
    'SERVICE_STARTED',
    181,
    'COUNTER',
    'STANDARD',
    37,
    36,
    '["PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    181,
    480,
    'MET',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00050 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    '4db2b8b3-5137-4ce8-9c0e-ccf00fbd8861',
    'PED-0001',
    'PREPARATION_COMPLETED',
    241,
    'COUNTER',
    'STANDARD',
    36,
    36,
    '["PED-0008", "PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    181,
    480,
    'MET',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00051 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    '6baa713a-2d36-42af-8388-0a1be8f64133',
    'PED-0008',
    'SERVICE_STARTED',
    241,
    'DELIVERY',
    'URGENT',
    36,
    35,
    '["PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    241,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00052 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    '212b7b04-1745-40aa-86d4-ac27b85d592d',
    'PED-0008',
    'PREPARATION_COMPLETED',
    301,
    'DELIVERY',
    'URGENT',
    35,
    35,
    '["PED-0010", "PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    241,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00053 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    'aca94ccb-b93d-4abd-988b-1a1995109ca2',
    'PED-0010',
    'SERVICE_STARTED',
    301,
    'DELIVERY',
    'URGENT',
    35,
    34,
    '["PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    301,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00054 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    'fd37ce4c-b0d9-4d5b-8560-579fa04fd233',
    'PED-0010',
    'PREPARATION_COMPLETED',
    481,
    'DELIVERY',
    'URGENT',
    34,
    34,
    '["PED-0012", "PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    301,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00055 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    '8fe2aa4e-e850-48be-8ae7-c81ba5c183b7',
    'PED-0012',
    'SERVICE_STARTED',
    481,
    'DELIVERY',
    'URGENT',
    34,
    33,
    '["PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    481,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00056 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    'ea591b87-359e-48b9-9aa8-d08334376dda',
    'PED-0012',
    'PREPARATION_COMPLETED',
    661,
    'DELIVERY',
    'URGENT',
    33,
    33,
    '["PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0002", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    481,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00057 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    '87d86f0f-b893-419e-9220-5145e6f07fa0',
    'PED-0002',
    'SERVICE_STARTED',
    661,
    'PICKUP',
    'STANDARD',
    33,
    32,
    '["PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    661,
    300,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00058 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    '4580888d-cc14-4fa9-8bfa-2511e342caae',
    'PED-0002',
    'PREPARATION_COMPLETED',
    721,
    'PICKUP',
    'STANDARD',
    32,
    32,
    '["PED-0013", "PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    661,
    300,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00059 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    '11b772c3-ce61-4a36-869b-eedb8093a0fb',
    'PED-0013',
    'SERVICE_STARTED',
    721,
    'DELIVERY',
    'URGENT',
    32,
    31,
    '["PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    721,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00060 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    'c4b0b486-e10f-4dbb-a5c5-5123fb1c7e0a',
    'PED-0013',
    'PREPARATION_COMPLETED',
    781,
    'DELIVERY',
    'URGENT',
    31,
    31,
    '["PED-0015", "PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    721,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00061 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    'a9f5e863-1bec-46b4-9d88-004d256ff38c',
    'PED-0015',
    'SERVICE_STARTED',
    781,
    'DELIVERY',
    'URGENT',
    31,
    30,
    '["PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    781,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00062 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    'cc1bb446-a463-4fca-abde-5384c32726c6',
    'PED-0015',
    'PREPARATION_COMPLETED',
    901,
    'DELIVERY',
    'URGENT',
    30,
    30,
    '["PED-0016", "PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    781,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00063 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    'af210be4-04d1-4ab7-8e4e-b86779fa77e5',
    'PED-0016',
    'SERVICE_STARTED',
    901,
    'DELIVERY',
    'URGENT',
    30,
    29,
    '["PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    901,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00064 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    '7c67194c-5f7b-4b93-ac5c-26a2ad279d8c',
    'PED-0016',
    'PREPARATION_COMPLETED',
    961,
    'DELIVERY',
    'URGENT',
    29,
    29,
    '["PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0004", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    901,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00065 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    'febdb921-2f24-45f8-a77f-fa2b3aab855f',
    'PED-0004',
    'SERVICE_STARTED',
    961,
    'COUNTER',
    'STANDARD',
    29,
    28,
    '["PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    961,
    480,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00066 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    '308456f3-164f-41fe-b803-ae4be786788e',
    'PED-0004',
    'PREPARATION_COMPLETED',
    1141,
    'COUNTER',
    'STANDARD',
    28,
    28,
    '["PED-0017", "PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    961,
    480,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00067 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    '92764ac2-f065-4486-9ff5-9e59ea42eb40',
    'PED-0017',
    'SERVICE_STARTED',
    1141,
    'DELIVERY',
    'URGENT',
    28,
    27,
    '["PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    1141,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00068 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    'd83cf83b-84aa-4d4c-90f1-8dce030355f8',
    'PED-0017',
    'PREPARATION_COMPLETED',
    1261,
    'DELIVERY',
    'URGENT',
    27,
    27,
    '["PED-0018", "PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    1141,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00069 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    '0f65e377-478d-46b6-b1d2-d416ae2ad0b4',
    'PED-0018',
    'SERVICE_STARTED',
    1261,
    'DELIVERY',
    'URGENT',
    27,
    26,
    '["PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    1261,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00070 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    '19021b7d-ec76-486f-8c4a-fd1e8c1d7bcb',
    'PED-0018',
    'PREPARATION_COMPLETED',
    1321,
    'DELIVERY',
    'URGENT',
    26,
    26,
    '["PED-0019", "PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    1261,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00071 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    'd4040ea2-3db7-446e-95ad-aa91b07227c0',
    'PED-0019',
    'SERVICE_STARTED',
    1321,
    'DELIVERY',
    'URGENT',
    26,
    25,
    '["PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    1321,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00072 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    'fdece181-c2cd-44fe-bbd4-00f2bdc0206f',
    'PED-0019',
    'PREPARATION_COMPLETED',
    1381,
    'DELIVERY',
    'URGENT',
    25,
    25,
    '["PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0005", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    1321,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00073 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    'a4fc7e66-f6ed-4d80-bdb5-3c953f62f031',
    'PED-0005',
    'SERVICE_STARTED',
    1381,
    'COUNTER',
    'STANDARD',
    25,
    24,
    '["PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    1381,
    480,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00074 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    '3a8f19e6-e7ab-43e5-9baa-82731cf64f63',
    'PED-0005',
    'PREPARATION_COMPLETED',
    1561,
    'COUNTER',
    'STANDARD',
    24,
    24,
    '["PED-0020", "PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    1381,
    480,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00075 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    'a287188f-4caa-4fe3-8eb6-e33eb4546e65',
    'PED-0020',
    'SERVICE_STARTED',
    1561,
    'DELIVERY',
    'URGENT',
    24,
    23,
    '["PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    1561,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00076 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    '8cba64d2-5696-4257-b778-58b733f0ab28',
    'PED-0020',
    'PREPARATION_COMPLETED',
    1681,
    'DELIVERY',
    'URGENT',
    23,
    23,
    '["PED-0023", "PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    1561,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00077 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    '6453aa9a-d11b-4227-b4ab-6c7faebc53a4',
    'PED-0023',
    'SERVICE_STARTED',
    1681,
    'DELIVERY',
    'URGENT',
    23,
    22,
    '["PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    1681,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00078 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    'c6d23376-8639-4553-bd66-b39f5542854e',
    'PED-0023',
    'PREPARATION_COMPLETED',
    1801,
    'DELIVERY',
    'URGENT',
    22,
    22,
    '["PED-0024", "PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    1681,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00079 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    'b5d91ac6-1f16-4867-9f4a-0d9a73a9b937',
    'PED-0024',
    'SERVICE_STARTED',
    1801,
    'DELIVERY',
    'URGENT',
    22,
    21,
    '["PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    1801,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00080 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    '0fb835b0-3ee9-4ee9-b6f5-e961298b384a',
    'PED-0024',
    'PREPARATION_COMPLETED',
    1981,
    'DELIVERY',
    'URGENT',
    21,
    21,
    '["PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0009", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    1801,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00081 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    '8658da6c-c310-431b-a50b-cc2724cb32f4',
    'PED-0009',
    'SERVICE_STARTED',
    1981,
    'COUNTER',
    'STANDARD',
    21,
    20,
    '["PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    1981,
    480,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00082 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    '1fb37e77-22b1-40d7-a80a-7a682a1ae8d3',
    'PED-0009',
    'PREPARATION_COMPLETED',
    2161,
    'COUNTER',
    'STANDARD',
    20,
    20,
    '["PED-0025", "PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    1981,
    480,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00083 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    'aa856a75-6e87-4b10-94b8-a82a75618c22',
    'PED-0025',
    'SERVICE_STARTED',
    2161,
    'DELIVERY',
    'URGENT',
    20,
    19,
    '["PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    2161,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00084 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    'fd1ba2a0-ed47-4502-b289-7c3f8e2307b1',
    'PED-0025',
    'PREPARATION_COMPLETED',
    2341,
    'DELIVERY',
    'URGENT',
    19,
    19,
    '["PED-0027", "PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    2161,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00085 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    '4fabeaf2-6971-4bc3-8919-9cdda0940f33',
    'PED-0027',
    'SERVICE_STARTED',
    2341,
    'DELIVERY',
    'URGENT',
    19,
    18,
    '["PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    2341,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00086 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    '72bea37c-a088-40df-8ede-de3f072f6737',
    'PED-0027',
    'PREPARATION_COMPLETED',
    2521,
    'DELIVERY',
    'URGENT',
    18,
    18,
    '["PED-0028", "PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    2341,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00087 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    '86cd1e16-f768-420e-81a5-e1ea894eae09',
    'PED-0028',
    'SERVICE_STARTED',
    2521,
    'DELIVERY',
    'URGENT',
    18,
    17,
    '["PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    2521,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00088 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    'a8910c2d-1b36-49b7-b6da-f204efbdd6d6',
    'PED-0028',
    'PREPARATION_COMPLETED',
    2581,
    'DELIVERY',
    'URGENT',
    17,
    17,
    '["PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0011", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    2521,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00089 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    '0a3141b1-2024-44ee-8067-7cc074581459',
    'PED-0011',
    'SERVICE_STARTED',
    2581,
    'PICKUP',
    'STANDARD',
    17,
    16,
    '["PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    2581,
    300,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00090 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    '52f28d4f-d00c-41d3-8cd3-52ea37d45db5',
    'PED-0011',
    'PREPARATION_COMPLETED',
    2641,
    'PICKUP',
    'STANDARD',
    16,
    16,
    '["PED-0030", "PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    2581,
    300,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00091 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    '462ec676-6c7b-4aa0-832d-55729274a87e',
    'PED-0030',
    'SERVICE_STARTED',
    2641,
    'DELIVERY',
    'URGENT',
    16,
    15,
    '["PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    2641,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00092 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    'f34c7ce0-a2e3-4cf3-a977-1d2d7c68be9e',
    'PED-0030',
    'PREPARATION_COMPLETED',
    2701,
    'DELIVERY',
    'URGENT',
    15,
    15,
    '["PED-0031", "PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    2641,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00093 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    '4c03bc15-0429-4f9d-9ccb-4e6eda2be290',
    'PED-0031',
    'SERVICE_STARTED',
    2701,
    'DELIVERY',
    'URGENT',
    15,
    14,
    '["PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    2701,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00094 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    'c9f91ea7-21ef-40ad-bd68-970d9b6318e9',
    'PED-0031',
    'PREPARATION_COMPLETED',
    2821,
    'DELIVERY',
    'URGENT',
    14,
    14,
    '["PED-0032", "PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    2701,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00095 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    'c9a5ef5d-d598-4531-995a-34cf33bc5e8e',
    'PED-0032',
    'SERVICE_STARTED',
    2821,
    'DELIVERY',
    'URGENT',
    14,
    13,
    '["PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    2821,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00096 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    'dafa4bf3-9b35-40b7-9b2b-04aa13e97d19',
    'PED-0032',
    'PREPARATION_COMPLETED',
    2941,
    'DELIVERY',
    'URGENT',
    13,
    13,
    '["PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0014", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    2821,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00097 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    '066c41f1-6b0e-460d-b461-5feacae44665',
    'PED-0014',
    'SERVICE_STARTED',
    2941,
    'COUNTER',
    'STANDARD',
    13,
    12,
    '["PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    2941,
    480,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00098 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    '65d9acc1-6bb0-41b6-bf2e-5b9081823e09',
    'PED-0014',
    'PREPARATION_COMPLETED',
    3121,
    'COUNTER',
    'STANDARD',
    12,
    12,
    '["PED-0034", "PED-0035", "PED-0036", "PED-0040", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    2941,
    480,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00099 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    '042b2ef1-9003-4de4-a999-ab8690f0dfdf',
    'PED-0034',
    'SERVICE_STARTED',
    3121,
    'DELIVERY',
    'URGENT',
    12,
    11,
    '["PED-0035", "PED-0036", "PED-0040", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    3121,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00100 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    '9b927980-6d00-41e4-8c1a-8a9db7e0bb79',
    'PED-0034',
    'PREPARATION_COMPLETED',
    3241,
    'DELIVERY',
    'URGENT',
    11,
    11,
    '["PED-0035", "PED-0036", "PED-0040", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    3121,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00101 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    'e572aa9b-9962-40cb-bd30-6517830d492c',
    'PED-0035',
    'SERVICE_STARTED',
    3241,
    'DELIVERY',
    'URGENT',
    11,
    10,
    '["PED-0036", "PED-0040", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    3241,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00102 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    '485e9894-d882-49f8-a622-33a0a09a401a',
    'PED-0035',
    'PREPARATION_COMPLETED',
    3421,
    'DELIVERY',
    'URGENT',
    10,
    10,
    '["PED-0036", "PED-0040", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    3241,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00103 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    'd3e82442-a155-4f9b-9792-6946d3a758bc',
    'PED-0036',
    'SERVICE_STARTED',
    3421,
    'DELIVERY',
    'URGENT',
    10,
    9,
    '["PED-0040", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    3421,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00104 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    'df87699a-7d33-463b-8a7f-8b0216a82197',
    'PED-0036',
    'PREPARATION_COMPLETED',
    3601,
    'DELIVERY',
    'URGENT',
    9,
    9,
    '["PED-0040", "PED-0021", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    3421,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00105 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    '394e717b-3f55-47a6-849c-117135fb5735',
    'PED-0021',
    'SERVICE_STARTED',
    3601,
    'PICKUP',
    'STANDARD',
    9,
    8,
    '["PED-0040", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    3601,
    300,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00106 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    '9659359c-767c-4521-86dc-7ab05867d47f',
    'PED-0021',
    'PREPARATION_COMPLETED',
    3661,
    'PICKUP',
    'STANDARD',
    8,
    8,
    '["PED-0040", "PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    3601,
    300,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00107 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    'ae2f92be-2baa-4c12-a716-04bfe3675355',
    'PED-0040',
    'SERVICE_STARTED',
    3661,
    'DELIVERY',
    'URGENT',
    8,
    7,
    '["PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    3661,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00108 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    '1ce36e70-d4fe-4830-8a7c-f40b929a760a',
    'PED-0040',
    'PREPARATION_COMPLETED',
    3781,
    'DELIVERY',
    'URGENT',
    7,
    7,
    '["PED-0022", "PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    3661,
    180,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00109 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    'a6db8140-7377-420b-a787-ab59b8bcece1',
    'PED-0022',
    'SERVICE_STARTED',
    3781,
    'PICKUP',
    'STANDARD',
    7,
    6,
    '["PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    3781,
    300,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00110 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    '2f33a8c7-df32-44fa-ab1a-c3eb505a140a',
    'PED-0022',
    'PREPARATION_COMPLETED',
    3961,
    'PICKUP',
    'STANDARD',
    6,
    6,
    '["PED-0026", "PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    3781,
    300,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00111 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    '7056e63a-b321-4e3c-966e-a1269f4b9a87',
    'PED-0026',
    'SERVICE_STARTED',
    3961,
    'PICKUP',
    'STANDARD',
    6,
    5,
    '["PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    3961,
    300,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00112 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    '77636ac0-58f8-4375-ad41-ef38d64db47f',
    'PED-0026',
    'PREPARATION_COMPLETED',
    4141,
    'PICKUP',
    'STANDARD',
    5,
    5,
    '["PED-0029", "PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    3961,
    300,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00113 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    '88e13235-e49a-41f1-b781-70385fe2d2cb',
    'PED-0029',
    'SERVICE_STARTED',
    4141,
    'COUNTER',
    'STANDARD',
    5,
    4,
    '["PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    4141,
    480,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00114 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    '2f6ef904-6c0e-4bc2-8153-bb30751ec453',
    'PED-0029',
    'PREPARATION_COMPLETED',
    4261,
    'COUNTER',
    'STANDARD',
    4,
    4,
    '["PED-0033", "PED-0037", "PED-0038", "PED-0039"]',
    4141,
    480,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00115 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    '0471843b-6cc4-4387-b623-a36832a674d2',
    'PED-0033',
    'SERVICE_STARTED',
    4261,
    'PICKUP',
    'STANDARD',
    4,
    3,
    '["PED-0037", "PED-0038", "PED-0039"]',
    4261,
    300,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00116 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    '66517f01-ba2c-4ca5-8bdf-5812e3361e3d',
    'PED-0033',
    'PREPARATION_COMPLETED',
    4321,
    'PICKUP',
    'STANDARD',
    3,
    3,
    '["PED-0037", "PED-0038", "PED-0039"]',
    4261,
    300,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00117 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    '33e90390-d288-477b-9b44-82a3ced1b4c9',
    'PED-0037',
    'SERVICE_STARTED',
    4321,
    'COUNTER',
    'STANDARD',
    3,
    2,
    '["PED-0038", "PED-0039"]',
    4321,
    480,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00118 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    '687b3abc-1d35-4e82-b46c-f75abfcd40a6',
    'PED-0037',
    'PREPARATION_COMPLETED',
    4501,
    'COUNTER',
    'STANDARD',
    2,
    2,
    '["PED-0038", "PED-0039"]',
    4321,
    480,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00119 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    '780c6510-c02e-4116-ae16-28fa33f34f98',
    'PED-0038',
    'SERVICE_STARTED',
    4501,
    'COUNTER',
    'STANDARD',
    2,
    1,
    '["PED-0039"]',
    4501,
    480,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00120 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    'a311b68e-016a-4112-91bc-57196278289d',
    'PED-0038',
    'PREPARATION_COMPLETED',
    4681,
    'COUNTER',
    'STANDARD',
    1,
    1,
    '["PED-0039"]',
    4501,
    480,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00121 | evento de fila | SERVICE_STARTED
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
    sla_status,
    recorded_at
) VALUES (
    '2ffa0de3-f809-4002-be58-3e86836bdbda',
    'PED-0039',
    'SERVICE_STARTED',
    4681,
    'COUNTER',
    'STANDARD',
    1,
    0,
    '[]',
    4681,
    480,
    'BREACHED',
    '2026-11-17 16:40:32'
);

-- Registro de auditoria #00122 | evento de fila | PREPARATION_COMPLETED
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
    sla_status,
    recorded_at
) VALUES (
    '65aae5a6-bc81-4c53-98b1-6a6130cdb4e4',
    'PED-0039',
    'PREPARATION_COMPLETED',
    4741,
    'COUNTER',
    'STANDARD',
    0,
    0,
    '[]',
    4681,
    480,
    'BREACHED',
    '2026-11-17 16:40:32'
);

COMMIT;
