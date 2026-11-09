-- =============================================================
-- Exportação de auditoria da fila de prioridade para fast food
-- Exemplo de histórico executável gerado pelo AuditLogger (Etapa 6)
-- =============================================================
BEGIN TRANSACTION;
INSERT INTO queue_events (event_id, ticket_id, event_type, simulated_second, channel, priority, queue_size_before, queue_size_after, queue_snapshot, wait_seconds, sla_target_seconds, sla_status) VALUES ('evt-001', 'ord-101', 'ENQUEUED', 0, 'DELIVERY', 'URGENT', 0, 1, '["ord-101"]', NULL, 180, NULL);
INSERT INTO queue_events (event_id, ticket_id, event_type, simulated_second, channel, priority, queue_size_before, queue_size_after, queue_snapshot, wait_seconds, sla_target_seconds, sla_status) VALUES ('evt-002', 'ord-102', 'ENQUEUED', 10, 'COUNTER', 'STANDARD', 1, 2, '["ord-101", "ord-102"]', NULL, 480, NULL);
INSERT INTO queue_events (event_id, ticket_id, event_type, simulated_second, channel, priority, queue_size_before, queue_size_after, queue_snapshot, wait_seconds, sla_target_seconds, sla_status) VALUES ('evt-003', 'ord-101', 'SERVICE_STARTED', 15, 'DELIVERY', 'URGENT', 2, 1, '["ord-102"]', 15, 180, 'MET');
INSERT INTO queue_events (event_id, ticket_id, event_type, simulated_second, channel, priority, queue_size_before, queue_size_after, queue_snapshot, wait_seconds, sla_target_seconds, sla_status) VALUES ('evt-004', 'ord-101', 'PREPARATION_COMPLETED', 75, 'DELIVERY', 'URGENT', 1, 1, '["ord-102"]', 15, 180, 'MET');
INSERT INTO queue_events (event_id, ticket_id, event_type, simulated_second, channel, priority, queue_size_before, queue_size_after, queue_snapshot, wait_seconds, sla_target_seconds, sla_status) VALUES ('evt-005', 'ord-102', 'SERVICE_STARTED', 75, 'COUNTER', 'STANDARD', 1, 0, '[]', 65, 480, 'MET');
INSERT INTO queue_events (event_id, ticket_id, event_type, simulated_second, channel, priority, queue_size_before, queue_size_after, queue_snapshot, wait_seconds, sla_target_seconds, sla_status) VALUES ('evt-006', 'ord-102', 'PREPARATION_COMPLETED', 195, 'COUNTER', 'STANDARD', 0, 0, '[]', 65, 480, 'MET');
COMMIT;
