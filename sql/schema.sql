
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
CREATE TRIGGER IF NOT EXISTS queue_events_no_UPDATE BEFORE UPDATE ON queue_events BEGIN SELECT RAISE(ABORT, 'Historico append-only'); END;
CREATE TRIGGER IF NOT EXISTS queue_events_no_DELETE BEFORE DELETE ON queue_events BEGIN SELECT RAISE(ABORT, 'Historico append-only'); END;
CREATE TRIGGER IF NOT EXISTS simulation_actions_no_UPDATE BEFORE UPDATE ON simulation_actions BEGIN SELECT RAISE(ABORT, 'Historico append-only'); END;
CREATE TRIGGER IF NOT EXISTS simulation_actions_no_DELETE BEFORE DELETE ON simulation_actions BEGIN SELECT RAISE(ABORT, 'Historico append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_sequence_no_UPDATE BEFORE UPDATE ON audit_sequence BEGIN SELECT RAISE(ABORT, 'Historico append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_sequence_no_DELETE BEFORE DELETE ON audit_sequence BEGIN SELECT RAISE(ABORT, 'Historico append-only'); END;
