"""Testes automatizados da Etapa 3 — Estrutura da fila."""

import unittest

from fastfood.domain.enums import PriorityLevel
from fastfood.domain.order import Order
from fastfood.domain.ticket import Ticket
from fastfood.queues.priority_queue import PriorityQueue


class PriorityQueueTests(unittest.TestCase):
    
    def setUp(self) -> None:
        """Inicializa uma nova fila vazia antes de cada teste."""
        self.queue = PriorityQueue()
        
        # Criação de pedidos didáticos baseada na Etapa 2
        order_urgent = Order("PED-URG", "delivery", "simple", arrival_time=10, courier_waiting=True)
        order_std1 = Order("PED-STD-1", "counter", "medium", arrival_time=15, courier_waiting=False)
        order_std2 = Order("PED-STD-2", "pickup", "complex", arrival_time=20, courier_waiting=False)
        
        self.ticket_urgent = Ticket(order_urgent, sequence=1)
        self.ticket_std1 = Ticket(order_std1, sequence=2)
        self.ticket_std2 = Ticket(order_std2, sequence=3)

    def test_enqueue_distributes_by_priority(self) -> None:
        """Os tickets devem ser direcionados corretamente para a faixa de sua prioridade."""
        self.queue.enqueue(self.ticket_urgent)
        self.queue.enqueue(self.ticket_std1)
        
        self.assertTrue(self.queue.has_waiting(PriorityLevel.URGENT))
        self.assertTrue(self.queue.has_waiting(PriorityLevel.STANDARD))

    def test_pop_oldest_respects_fifo(self) -> None:
        """A remoção dentro de uma faixa específica deve respeitar a ordem de chegada (FIFO)."""
        self.queue.enqueue(self.ticket_std1)
        self.queue.enqueue(self.ticket_std2)
        
        # O ticket_std1 entrou primeiro, logo deve sair primeiro.
        removed_first = self.queue.pop_oldest(PriorityLevel.STANDARD)
        self.assertIs(removed_first, self.ticket_std1)
        
        removed_second = self.queue.pop_oldest("STANDARD")
        self.assertIs(removed_second, self.ticket_std2)

    def test_pop_from_empty_queue_raises_error(self) -> None:
        """Tentar remover de uma fila vazia deve levantar um IndexError claro."""
        with self.assertRaisesRegex(IndexError, "Não há tickets aguardando na faixa URGENT"):
            self.queue.pop_oldest(PriorityLevel.URGENT)

    def test_invalid_priority_raises_value_error(self) -> None:
        """Consultar ou retirar com prioridade inexistente deve ser bloqueado."""
        with self.assertRaisesRegex(ValueError, "Prioridade desconhecida"):
            self.queue.has_waiting("VIP")
            
        with self.assertRaisesRegex(ValueError, "Prioridade desconhecida"):
            self.queue.pop_oldest("SUPER_URGENT")

    def test_snapshot_preserves_queue_state(self) -> None:
        """O método snapshot deve listar todos os tickets sem removê-los das deques."""
        self.queue.enqueue(self.ticket_urgent)
        self.queue.enqueue(self.ticket_std1)
        
        snapshot = self.queue.snapshot()
        
        self.assertEqual(len(snapshot), 2)
        self.assertIn(self.ticket_urgent, snapshot)
        self.assertIn(self.ticket_std1, snapshot)
        
        # Confirma que as filas originais não foram esvaziadas pelo snapshot
        self.assertTrue(self.queue.has_waiting(PriorityLevel.URGENT))
        self.assertTrue(self.queue.has_waiting(PriorityLevel.STANDARD))

    def test_enqueue_invalid_object_raises_type_error(self) -> None:
        """Impede que objetos que não são Tickets sejam adicionados à fila."""
        with self.assertRaises(TypeError):
            self.queue.enqueue("Ticket Falso")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()