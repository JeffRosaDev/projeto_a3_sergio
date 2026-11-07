"""Políticas que escolhem a próxima faixa de atendimento."""

from abc import ABC, abstractmethod

from fastfood.domain.enums import PriorityLevel
from fastfood.domain.rules import BusinessRules
from fastfood.queues.priority_queue import PriorityQueue


class PriorityPolicy(ABC):
    """Contrato usado pelo despachante para escolher uma faixa e registrar inícios."""

    @abstractmethod
    def choose_priority(self, queue: PriorityQueue) -> PriorityLevel | None:
        """Escolhe uma faixa sem alterar a fila ou o estado da política."""

    @abstractmethod
    def record_started(self, priority: PriorityLevel) -> None:
        """Registra a prioridade de um ticket após o início do preparo."""


class QuotaFairnessPolicy(PriorityPolicy):
    """Limita os inícios urgentes consecutivos quando há pedidos padrão."""

    def __init__(self, rules: BusinessRules | None = None) -> None:
        if rules is None:
            rules = BusinessRules()
        self._urgent_quota = rules.urgent_quota
        self._consecutive_urgent_starts = 0

    def choose_priority(self, queue: PriorityQueue) -> PriorityLevel | None:
        has_urgent = queue.has_waiting(PriorityLevel.URGENT)
        if has_urgent and self._consecutive_urgent_starts < self._urgent_quota:
            return PriorityLevel.URGENT
        if queue.has_waiting(PriorityLevel.STANDARD):
            return PriorityLevel.STANDARD
        if has_urgent:
            return PriorityLevel.URGENT
        return None

    def record_started(self, priority: PriorityLevel) -> None:
        if not isinstance(priority, PriorityLevel):
            raise TypeError("priority deve ser PriorityLevel.")
        if priority is PriorityLevel.URGENT:
            self._consecutive_urgent_starts = min(
                self._consecutive_urgent_starts + 1, self._urgent_quota
            )
        else:
            self._consecutive_urgent_starts = 0
