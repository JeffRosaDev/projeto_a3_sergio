"""
Testes automatizados da Etapa 2 — Pedido, Ticket e Estados.

Objetivos:
- Validar a criação de pedidos.
- Verificar as prioridades atribuídas.
- Testar as mudanças de estado dos tickets.
- Impedir operações e horários inválidos.
- Garantir que o ticket preserve seu pedido original.

Para executar:
python -m unittest discover -s tests -p "test*.py" -v
"""

import unittest

from fastfood.domain.enums import PriorityLevel, TicketStatus
from fastfood.domain.order import Order
from fastfood.domain.ticket import Ticket


class TestOrderTicket(unittest.TestCase):
    """
    Testa as classes Order e Ticket.

    unittest.TestCase oferece métodos como:
    - assertEqual: compara dois valores.
    - assertRaises: verifica se um erro é lançado.
    - assertIs: verifica se dois objetos são o mesmo objeto.
    """

    # ==================================================
    # 1. TESTES DA CLASSE ORDER
    # ==================================================

    def test_order_valido(self):
        """Verifica se um pedido válido é criado corretamente."""

        pedido = Order(
            "PED-001", "delivery", "simple", 10, True
        )

        self.assertEqual(pedido.id, "PED-001")

    def test_horario_negativo(self):
        """Impede pedidos com horário de chegada negativo."""

        with self.assertRaises(ValueError):
            Order(
                "PED-002", "delivery", "simple", -1, False
            )

    def test_canal_invalido(self):
        """Rejeita canais que não existem em OrderChannel."""

        with self.assertRaises(ValueError):
            Order(
                "PED-003", "invalido", "simple", 0, False
            )

    def test_complexidade_invalida(self):
        """Rejeita complexidades não definidas no sistema."""

        with self.assertRaises(ValueError):
            Order(
                "PED-009", "delivery", "desconhecida", 0
            )

    # ==================================================
    # 2. TESTES DE PRIORIDADE
    # ==================================================

    def test_prioridade_urgente(self):
        """
        Delivery com entregador aguardando deve ser URGENT.
        A prioridade é calculada usando BusinessRules.
        """

        pedido = Order(
            "PED-004", "delivery", "simple", 0, True
        )

        ticket = Ticket(pedido, 1)

        self.assertEqual(
            ticket.priority,
            PriorityLevel.URGENT
        )

    def test_prioridade_normal(self):
        """
        Pedido de balcão deve receber prioridade STANDARD.
        """

        pedido = Order(
            "PED-005", "counter", "medium", 0, False
        )

        ticket = Ticket(pedido, 2)

        self.assertEqual(
            ticket.priority,
            PriorityLevel.STANDARD
        )

    # ==================================================
    # 3. TESTES DE ESTADOS DO TICKET
    # ==================================================

    def test_ciclo_de_vida(self):
        """
        Verifica o fluxo normal do atendimento:

        WAITING -> PREPARING -> COMPLETED
        """

        pedido = Order(
            "PED-006", "pickup", "simple", 10
        )

        ticket = Ticket(pedido, 1)

        # O ticket começa aguardando.
        self.assertEqual(
            ticket.status,
            TicketStatus.WAITING
        )

        # O preparo começa no segundo 20.
        ticket.start_preparation(20)

        self.assertEqual(
            ticket.status,
            TicketStatus.PREPARING
        )

        # O preparo termina no segundo 80.
        ticket.complete_preparation(80)

        self.assertEqual(
            ticket.status,
            TicketStatus.COMPLETED
        )

    def test_nao_concluir_sem_iniciar(self):
        """
        Um ticket não pode ser concluído
        antes de iniciar seu preparo.
        """

        pedido = Order(
            "PED-007", "counter", "simple", 0
        )

        ticket = Ticket(pedido, 1)

        with self.assertRaises(ValueError):
            ticket.complete_preparation(60)

    def test_cancelamento(self):
        """
        Um ticket em WAITING pode ser cancelado.

        Depois de CANCELLED, não pode iniciar preparo.
        """

        pedido = Order(
            "PED-008", "counter", "simple", 0
        )

        ticket = Ticket(pedido, 1)

        ticket.cancel()

        self.assertEqual(
            ticket.status,
            TicketStatus.CANCELLED
        )

        with self.assertRaises(ValueError):
            ticket.start_preparation(10)

    def test_nao_iniciar_duas_vezes(self):
        """
        Impede que o mesmo ticket
        inicie seu preparo duas vezes.
        """

        pedido = Order(
            "PED-013", "delivery", "simple", 0
        )

        ticket = Ticket(pedido, 1)

        ticket.start_preparation(10)

        with self.assertRaises(ValueError):
            ticket.start_preparation(20)

    def test_nao_cancelar_em_preparo(self):
        """
        Impede cancelar um ticket que
        já está sendo preparado.
        """

        pedido = Order(
            "PED-014", "pickup", "simple", 0
        )

        ticket = Ticket(pedido, 1)

        ticket.start_preparation(10)

        with self.assertRaises(ValueError):
            ticket.cancel()

    # ==================================================
    # 4. TESTES DE VALIDAÇÃO DE DADOS E HORÁRIOS
    # ==================================================

    def test_sequencia_invalida(self):
        """
        A sequência de chegada deve ser
        um número inteiro maior que zero.
        """

        pedido = Order(
            "PED-010", "counter", "simple", 0
        )

        with self.assertRaises(ValueError):
            Ticket(pedido, 0)

    def test_inicio_antes_da_chegada(self):
        """
        O preparo não pode começar antes
        do horário de entrada na fila.
        """

        pedido = Order(
            "PED-011", "pickup", "simple", 100
        )

        ticket = Ticket(pedido, 1)

        with self.assertRaises(ValueError):
            ticket.start_preparation(50)

        # Após a tentativa inválida,
        # o ticket deve continuar aguardando.
        self.assertEqual(
            ticket.status,
            TicketStatus.WAITING
        )

    def test_conclusao_antes_do_inicio(self):
        """
        O preparo não pode terminar
        antes de ter começado.
        """

        pedido = Order(
            "PED-012", "counter", "simple", 0
        )

        ticket = Ticket(pedido, 1)

        ticket.start_preparation(100)

        with self.assertRaises(ValueError):
            ticket.complete_preparation(50)

        # O estado deve permanecer PREPARING.
        self.assertEqual(
            ticket.status,
            TicketStatus.PREPARING
        )

    # ==================================================
    # 5. TESTE DE RELACIONAMENTO ENTRE OBJETOS
    # ==================================================

    def test_pedido_preservado_no_ticket(self):
        """
        Verifica se Ticket mantém a referência
        ao mesmo objeto Order recebido.

        Também confirma o horário de entrada
        e a prioridade atribuída.
        """

        pedido = Order(
            "PED-015", "delivery", "medium", 30, True
        )

        ticket = Ticket(pedido, 1)

        # assertIs verifica a identidade do objeto.
        self.assertIs(ticket.order, pedido)

        self.assertEqual(
            ticket.enqueued_at,
            30
        )

        self.assertEqual(
            ticket.priority,
            PriorityLevel.URGENT
        )


# Permite executar este arquivo diretamente.
if __name__ == "__main__":
    unittest.main()