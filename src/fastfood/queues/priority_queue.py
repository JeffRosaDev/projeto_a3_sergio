"""Estrutura da fila que armazena os tickets em faixas FIFO separadas."""

from collections import deque

from fastfood.domain.enums import PriorityLevel
from fastfood.domain.ticket import Ticket


class PriorityQueue:
    """
    Mantém filas independentes por faixa de prioridade.
    
    A inserção e remoção no início ou fim ocorrem em tempo O(1), enquanto
    a geração do snapshot da fila consome tempo O(n).
    """

    def __init__(self) -> None:
        self._queues: dict[PriorityLevel, deque[Ticket]] = {
            PriorityLevel.URGENT: deque(),
            PriorityLevel.STANDARD: deque(),
        }

    def enqueue(self, ticket: Ticket) -> None:
        """Insere um ticket no final da faixa correspondente à sua prioridade."""
        if not isinstance(ticket, Ticket):
            raise TypeError("Apenas objetos Ticket podem ser enfileirados.")
            
        self._queues[ticket.priority].append(ticket)

    def has_waiting(self, priority: PriorityLevel | str) -> bool:
        """Indica se há tickets aguardando na prioridade informada."""
        priority_enum = self._validate_priority(priority)
        return len(self._queues[priority_enum]) > 0

    def pop_oldest(self, priority: PriorityLevel | str) -> Ticket:
        """
        Retira e devolve o ticket mais antigo da prioridade informada.
        Levanta exceção clara caso a fila solicitada esteja vazia.
        """
        priority_enum = self._validate_priority(priority)

        if not self.has_waiting(priority_enum):
            raise IndexError(f"Não há tickets aguardando na faixa {priority_enum.value}.")

        return self._queues[priority_enum].popleft()

    def snapshot(self) -> list[Ticket]:
        """
        Devolve um retrato imutável contendo todos os tickets em espera.
        A ordem apresentada prioriza visualmente a lista de urgentes seguida da padrão, 
        sem alterar o estado das deques.
        """
        return list(self._queues[PriorityLevel.URGENT]) + list(self._queues[PriorityLevel.STANDARD])

    @staticmethod
    def _validate_priority(priority: PriorityLevel | str) -> PriorityLevel:
        """Garante que apenas prioridades conhecidas e válidas sejam consultadas."""
        if isinstance(priority, PriorityLevel):
            return priority
            
        if not isinstance(priority, str):
            raise TypeError("priority deve ser texto ou PriorityLevel.")
            
        try:
            return PriorityLevel(priority.strip().upper())
        except ValueError as error:
            raise ValueError(f"Prioridade desconhecida: {priority!r}.") from error