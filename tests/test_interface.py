"""Interações reais com widgets via Streamlit AppTest."""

import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


class InterfaceTests(unittest.TestCase):
    """Checa persistência entre reruns, erros legíveis e operações da interface."""

    def setUp(self):
        self.app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=20
        ).run()
        self.addCleanup(lambda: self.app.session_state.engine.audit_logger.close())
        self.assertFalse(self.app.exception)

    def button(self, label):
        return next(b for b in self.app.button if b.label == label)

    def test_create_duplicate_then_advance_and_cancel(self):
        self.app.text_input(key="order_id").set_value("CHECK")
        self.button("Adicionar à fila").click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual(len(self.app.session_state.engine.tickets), 1)
        self.app.text_input(key="order_id").set_value("CHECK")
        self.button("Adicionar à fila").click().run()
        self.assertTrue(self.app.error)
        self.assertEqual(len(self.app.session_state.engine.tickets), 1)
        self.app.button(key="step1").click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.app.session_state.engine.preparing_ticket.id, "CHECK")
        self.app.button(key="step60").click().run()
        self.assertEqual(
            self.app.session_state.engine.tickets["CHECK"].status.value, "COMPLETED"
        )

    def test_lab_burst_pause_adjust_and_export(self):
        self.app.button(key="burst").click().run()
        self.app.button(key="step1").click().run()
        self.app.number_input(key="prep_SIMPLE").set_value(10)
        self.app.number_input(key="quota").set_value(1)
        self.button("Aplicar parâmetros").click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.app.session_state.engine.rules.urgent_quota, 1)
        self.app.button(key="pause_station").click().run()
        self.app.button(key="step60").click().run()
        self.assertEqual(self.app.session_state.engine.current_time, 61)
        self.assertEqual(self.app.session_state.engine.preparation_end_time, 121)
        self.app.number_input(key="remaining").set_value(2)
        self.button("Ajustar preparo atual").click().run()
        self.app.button(key="pause_station").click().run()
        self.app.button(key="step60").click().run()
        self.assertFalse(self.app.exception)
        self.assertIn(
            "CONFIG_CHANGED", self.app.session_state.engine.audit_logger.export_sql()
        )

    def test_reset_requires_confirmation(self):
        self.assertTrue(self.app.button(key="reset").disabled)
        self.app.button(key="burst").click().run()
        self.app.checkbox(key="reset_confirm").check().run()
        self.app.button(key="reset").click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual(len(self.app.session_state.engine.tickets), 0)
        # Uma falha automática precisa parar a reprodução e continuar visível após rerun.
        engine = self.app.session_state.engine
        with (
            patch.object(engine, "advance", side_effect=ValueError("Falha simulada")),
            patch("fastfood.services.playback.PlaybackClock.consume", return_value=5),
        ):
            self.app.button(key="play").click().run()
        self.assertFalse(self.app.exception)
        self.assertFalse(self.app.session_state.auto)
        self.assertTrue(any("Falha simulada" in e.value for e in self.app.error))

    def test_start_pause_and_draft_preserved(self):
        """O controle principal inicia/pausa; um erro de pedido não apaga seu ID."""
        self.app.button(key="burst").click().run()
        with patch("fastfood.services.playback.PlaybackClock.consume", return_value=5):
            self.app.button(key="play").click().run()
        self.assertTrue(self.app.session_state.auto)
        self.assertTrue(self.app.button(key="step1").disabled)
        self.assertEqual(self.app.session_state.engine.current_time, 5)
        self.app.button(key="play").click().run()
        self.app.run()
        self.assertFalse(self.app.session_state.auto)
        self.assertEqual(self.app.session_state.engine.current_time, 5)
        self.app.text_input(key="order_id").set_value("PED-0001")
        self.button("Adicionar à fila").click().run()
        self.assertTrue(self.app.error)
        self.assertEqual(self.app.text_input(key="order_id").value, "PED-0001")

    def test_hidden_history_does_not_export_on_each_operation_update(self):
        """O painel automático não deve regenerar o SQL de uma aba escondida."""
        logger = self.app.session_state.engine.audit_logger
        with patch.object(logger, "export_sql", wraps=logger.export_sql) as export:
            self.app.run()
            export.assert_not_called()

    def test_audit_tab_includes_events_and_operator_commands(self):
        """A trilha une eventos e ações, com ordem explícita e filtros de texto."""
        self.app.button(key="burst").click().run()
        self.app.button(key="step1").click().run()
        self.app.session_state.workspace = "Logs e auditoria"
        self.app.run()
        self.assertFalse(self.app.exception)
        timeline = self.app.session_state.engine.audit_logger.timeline()
        self.assertEqual(
            [r["sequence"] for r in timeline], list(range(1, len(timeline) + 1))
        )
        self.assertTrue(
            {"CONFIG_INITIAL", "ENQUEUED", "SERVICE_STARTED", "BURST", "TIME_ADVANCED"}
            <= {r["operation"] for r in timeline}
        )
        self.app.text_input(key="log_search").set_value("PED-0001").run()
        self.assertFalse(self.app.exception)
        self.assertTrue(len(self.app.dataframe[-1].value) > 0)
