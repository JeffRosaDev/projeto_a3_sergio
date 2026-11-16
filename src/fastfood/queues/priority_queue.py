"""Estrutura da fila que armazena os tickets em faixas FIFO separadas."""

from collections import deque

from fastfood.domain.enums import PriorityLevel, TicketStatus
from fastfood.domain.ticket import Ticket


class PriorityQueue:
    """
    Mantém filas independentes por faixa de prioridade.

    A inserção e remoção no início ou fim ocorrem em tempo O(1), enquanto
    a geração do snapshot da fila consome tempo O(n).
    """

    def __init__(self) -> None:
        """Cria uma deque por faixa e o índice de IDs atualmente aguardando."""
        self._ids: set[str] = set()  # Evita duplicidade em O(1).
        self._queues: dict[PriorityLevel, deque[Ticket]] = {
            PriorityLevel.URGENT: deque(),
            PriorityLevel.STANDARD: deque(),
        }

    def enqueue(self, ticket: Ticket) -> None:
        """Insere um ticket no final da faixa correspondente à sua prioridade."""
        if not isinstance(ticket, Ticket):
            raise TypeError("Apenas objetos Ticket podem ser enfileirados.")

        if ticket.status is not TicketStatus.WAITING:
            raise ValueError("Somente tickets aguardando podem entrar na fila.")
        if ticket.id in self._ids:
            raise ValueError("ID já está na fila.")
        self._queues[self._validate_priority(ticket.priority)].append(ticket)
        self._ids.add(ticket.id)

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
            raise IndexError(
                f"Não há tickets aguardando na faixa {priority_enum.value}."
            )

        ticket = self._queues[priority_enum].popleft()
        self._ids.remove(ticket.id)
        return ticket

    def snapshot(self) -> list[Ticket]:
        """
        Devolve uma cópia da lista contendo todos os tickets em espera.
        A ordem apresentada prioriza visualmente a lista de urgentes seguida da padrão,
        sem alterar o estado das deques.
        """
        return list(self._queues[PriorityLevel.URGENT]) + list(
            self._queues[PriorityLevel.STANDARD]
        )

    def restore(self, tickets: list[Ticket]) -> None:
        """Restaura a ordem de um checkpoint após falha de transação."""
        self._ids = {t.id for t in tickets}
        for lane in self._queues.values():
            lane.clear()
        for ticket in tickets:
            self._queues[ticket.priority].append(ticket)

    def remove(self, ticket: Ticket) -> None:
        """Remove um ticket aguardando durante cancelamento auditado."""
        self._queues[ticket.priority].remove(ticket)
        self._ids.remove(ticket.id)

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
