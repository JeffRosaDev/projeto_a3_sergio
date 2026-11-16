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

    @abstractmethod
    def configure(self, rules: BusinessRules) -> None:
        """Aplica uma configuração preservando a justiça acumulada."""

    @abstractmethod
    def checkpoint(self) -> tuple[int, int]:
        """Devolve estado suficiente para reverter uma decisão."""

    @abstractmethod
    def restore(self, state: tuple[int, int]) -> None:
        """Restaura o estado salvo após falha de persistência."""


class QuotaFairnessPolicy(PriorityPolicy):
    """Limita os inícios urgentes consecutivos quando há pedidos padrão."""

    def __init__(self, rules: BusinessRules | None = None) -> None:
        """Inicializa a cota configurada e o contador de urgentes efetivamente iniciados."""
        if rules is None:
            rules = BusinessRules()
        self._urgent_quota = rules.urgent_quota
        self._consecutive_urgent_starts = 0

    def choose_priority(self, queue: PriorityQueue) -> PriorityLevel | None:
        """Consulta faixas e contador, sem consumir a oportunidade de atendimento."""
        has_urgent = queue.has_waiting(PriorityLevel.URGENT)
        if has_urgent and self._consecutive_urgent_starts < self._urgent_quota:
            return PriorityLevel.URGENT
        if queue.has_waiting(PriorityLevel.STANDARD):
            return PriorityLevel.STANDARD
        if has_urgent:
            return PriorityLevel.URGENT
        return None

    def record_started(self, priority: PriorityLevel) -> None:
        """Conta um início urgente ou reinicia a contagem quando um padrão começa."""
        if not isinstance(priority, PriorityLevel):
            raise TypeError("priority deve ser PriorityLevel.")
        if priority is PriorityLevel.URGENT:
            self._consecutive_urgent_starts = min(
                self._consecutive_urgent_starts + 1, self._urgent_quota
            )
        else:
            self._consecutive_urgent_starts = 0

    @property
    def consecutive_urgent_starts(self) -> int:
        """Quantidade de inícios urgentes desde o último padrão, limitada à cota."""
        return self._consecutive_urgent_starts

    def configure(self, rules: BusinessRules) -> None:
        """Altera a cota preservando a justiça acumulada, sem zerar o contador."""
        self._urgent_quota = rules.urgent_quota
        self._consecutive_urgent_starts = min(
            self._consecutive_urgent_starts, self._urgent_quota
        )

    def checkpoint(self) -> tuple[int, int]:
        """Copia contador e cota para recuperação transacional."""
        return self._urgent_quota, self._consecutive_urgent_starts

    def restore(self, state: tuple[int, int]) -> None:
        """Recupera contador e cota após uma operação rejeitada."""
        self._urgent_quota, self._consecutive_urgent_starts = state
