"""Interações reais com widgets via Streamlit AppTest."""

import unittest
from pathlib import Path

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
