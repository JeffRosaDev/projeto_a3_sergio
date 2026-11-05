"""Eventos imutáveis que conectam os serviços futuros à camada de auditoria."""

from dataclasses import dataclass

from .enums import OrderChannel, PriorityLevel, QueueEventType, SlaStatus


@dataclass(frozen=True, slots=True)
class QueueEvent:
    """Fato ocorrido na fila, com dados para reconstruir o fluxo.

    `queue_snapshot` lista os IDs que continuam esperando depois do evento. A
    camada SQLite poderá serializar essa tupla como JSON sem envolver a interface.
    """

    event_id: str
    ticket_id: str
    event_type: QueueEventType
    simulated_second: int
    channel: OrderChannel
    priority: PriorityLevel
    queue_size_before: int
    queue_size_after: int
    queue_snapshot: tuple[str, ...] = ()
    wait_seconds: int | None = None
    sla_target_seconds: int | None = None
    sla_status: SlaStatus | None = None

    def __post_init__(self) -> None:
        """Rejeita dados que tornariam impossível ordenar ou interpretar o log."""

        if not isinstance(self.event_id, str):
            raise TypeError("event_id deve ser texto.")
        if not self.event_id.strip():
            raise ValueError("event_id não pode ser vazio.")
        if not isinstance(self.ticket_id, str):
            raise TypeError("ticket_id deve ser texto.")
        if not self.ticket_id.strip():
            raise ValueError("ticket_id não pode ser vazio.")
        if not isinstance(self.event_type, QueueEventType):
            raise TypeError("event_type deve ser um valor de QueueEventType.")
        if not isinstance(self.channel, OrderChannel):
            raise TypeError("channel deve ser um valor de OrderChannel.")
        if not isinstance(self.priority, PriorityLevel):
            raise TypeError("priority deve ser um valor de PriorityLevel.")
        if not isinstance(self.simulated_second, int) or isinstance(
            self.simulated_second, bool
        ):
            raise TypeError("simulated_second deve ser um inteiro.")
        if self.simulated_second < 0:
            raise ValueError("simulated_second não pode ser negativo.")

        # Tamanho de fila é uma contagem e não pode ser fracionário ou negativo.
        for name, size in (
            ("queue_size_before", self.queue_size_before),
            ("queue_size_after", self.queue_size_after),
        ):
            if not isinstance(size, int) or isinstance(size, bool):
                raise TypeError(f"{name} deve ser um inteiro.")
            if size < 0:
                raise ValueError(f"{name} não pode ser negativo.")

        if not isinstance(self.queue_snapshot, tuple):
            raise TypeError("queue_snapshot deve ser uma tupla de IDs.")
        if any(
            not isinstance(ticket_id, str) or not ticket_id
            for ticket_id in self.queue_snapshot
        ):
            raise ValueError("queue_snapshot deve conter apenas IDs não vazios.")
        if len(self.queue_snapshot) != self.queue_size_after:
            raise ValueError("queue_snapshot deve corresponder a queue_size_after.")

        if self.wait_seconds is not None:
            self._validate_optional_seconds("wait_seconds", self.wait_seconds)
        if self.sla_target_seconds is not None:
            self._validate_optional_seconds("sla_target_seconds", self.sla_target_seconds)
        if self.sla_status is not None and not isinstance(self.sla_status, SlaStatus):
            raise TypeError("sla_status deve ser SlaStatus ou None.")

    @staticmethod
    def _validate_optional_seconds(name: str, value: int) -> None:
        """Valida um número opcional de segundos incluído no evento."""

        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"{name} deve ser um inteiro ou None.")
        if value < 0:
            raise ValueError(f"{name} não pode ser negativo.")
