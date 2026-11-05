"""Testes unitários para as regras simples e independentes do domínio."""

import unittest

from fastfood.domain import (
    BusinessRules,
    OrderChannel,
    OrderComplexity,
    PriorityLevel,
)


class BusinessRulesTests(unittest.TestCase):
    """Confere prioridade, tempos configuráveis e validação dos parâmetros."""

    def setUp(self) -> None:
        """Usa uma configuração padrão isolada para cada caso de teste."""

        self.rules = BusinessRules()

    def test_delivery_with_waiting_courier_is_urgent(self) -> None:
        """Delivery só recebe urgência quando o entregador já está aguardando."""

        self.assertIs(
            self.rules.priority_for("DELIVERY", courier_waiting=True),
            PriorityLevel.URGENT,
        )

    def test_delivery_without_waiting_courier_is_standard(self) -> None:
        """Um delivery sem entregador presente permanece na faixa padrão."""

        self.assertIs(
            self.rules.priority_for("DELIVERY", courier_waiting=False),
            PriorityLevel.STANDARD,
        )

    def test_non_delivery_channels_remain_standard(self) -> None:
        """A presença do indicador não torna retirada ou balcão urgentes."""

        for channel in ("PICKUP", "COUNTER"):
            with self.subTest(channel=channel):
                self.assertIs(
                    self.rules.priority_for(channel, courier_waiting=True),
                    PriorityLevel.STANDARD,
                )

    def test_simple_string_values_are_normalized(self) -> None:
        """Aceita textos simples em minúsculas e com espaços externos."""

        self.assertIs(
            self.rules.priority_for(" delivery ", courier_waiting=True),
            PriorityLevel.URGENT,
        )
        self.assertEqual(self.rules.sla_seconds_for("pickup"), 300)
        self.assertEqual(self.rules.preparation_seconds_for("complex"), 180)

    def test_enum_values_are_also_accepted(self) -> None:
        """Mantém compatibilidade com os enums usados pelos objetos da Etapa 2."""

        self.assertIs(
            self.rules.priority_for(OrderChannel.DELIVERY, courier_waiting=True),
            PriorityLevel.URGENT,
        )
        self.assertEqual(self.rules.sla_seconds_for(OrderChannel.COUNTER), 480)
        self.assertEqual(
            self.rules.preparation_seconds_for(OrderComplexity.MEDIUM),
            120,
        )

    def test_default_sla_and_preparation_parameters(self) -> None:
        """Confere os parâmetros didáticos usados na versão inicial."""

        expected_sla = {
            "DELIVERY": 180,
            "PICKUP": 300,
            "COUNTER": 480,
        }
        expected_preparation = {
            "SIMPLE": 60,
            "MEDIUM": 120,
            "COMPLEX": 180,
        }
        for channel, seconds in expected_sla.items():
            with self.subTest(channel=channel):
                self.assertEqual(self.rules.sla_seconds_for(channel), seconds)
        for complexity, seconds in expected_preparation.items():
            with self.subTest(complexity=complexity):
                self.assertEqual(
                    self.rules.preparation_seconds_for(complexity), seconds
                )

    def test_custom_parameters_are_copied_and_read_only(self) -> None:
        """Mudanças externas nos mapas não alteram a regra já construída."""

        sla = {
            OrderChannel.DELIVERY: 200,
            OrderChannel.PICKUP: 320,
            OrderChannel.COUNTER: 500,
        }
        rules = BusinessRules(sla_targets_seconds=sla, urgent_quota=4)
        sla[OrderChannel.DELIVERY] = 999

        self.assertEqual(rules.sla_seconds_for("DELIVERY"), 200)
        self.assertEqual(rules.urgent_quota, 4)
        with self.assertRaises(TypeError):
            rules.sla_targets_seconds[OrderChannel.DELIVERY] = 1  # type: ignore[index]

    def test_invalid_simple_values_raise_clear_errors(self) -> None:
        """Rejeita canais, complexidades e indicadores fora dos contratos."""

        with self.assertRaisesRegex(ValueError, "Canal desconhecido"):
            self.rules.priority_for("DRIVE_THRU", courier_waiting=False)
        with self.assertRaisesRegex(ValueError, "Complexidade desconhecida"):
            self.rules.preparation_seconds_for("GIANT")
        with self.assertRaises(TypeError):
            self.rules.priority_for("DELIVERY", courier_waiting="yes")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            self.rules.sla_seconds_for(1)  # type: ignore[arg-type]

    def test_invalid_configuration_is_rejected(self) -> None:
        """Impede metas, mapas, cota ou limiar que quebrariam o cálculo."""

        with self.assertRaisesRegex(ValueError, "maiores que zero"):
            BusinessRules(
                sla_targets_seconds={
                    OrderChannel.DELIVERY: 0,
                    OrderChannel.PICKUP: 300,
                    OrderChannel.COUNTER: 480,
                }
            )
        with self.assertRaisesRegex(ValueError, "chaves ausentes"):
            BusinessRules(sla_targets_seconds={OrderChannel.DELIVERY: 180})
        with self.assertRaisesRegex(ValueError, "urgent_quota"):
            BusinessRules(urgent_quota=0)
        with self.assertRaisesRegex(ValueError, "at_risk_fraction"):
            BusinessRules(at_risk_fraction=1.1)


if __name__ == "__main__":
    unittest.main()
