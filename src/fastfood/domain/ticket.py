"""Representa um pedido durante seu atendimento na fila."""

from dataclasses import dataclass, field

from .enums import PriorityLevel, TicketStatus
from .order import Order
from .rules import BusinessRules


@dataclass(slots=True)
class Ticket:
    order: Order
    sequence: int
    rules: BusinessRules = field(
        default_factory=BusinessRules,
        repr=False
    )

    priority: PriorityLevel = field(init=False)
    status: TicketStatus = field(
        default=TicketStatus.WAITING,
        init=False
    )
    enqueued_at: int = field(init=False)
    started_at: int | None = field(default=None, init=False)
    completed_at: int | None = field(default=None, init=False)

    @property
    def id(self) -> str:
        return self.order.id

    def __post_init__(self):
        if not isinstance(self.order, Order):
            raise TypeError("order deve ser um objeto Order.")

        if isinstance(self.sequence, bool) or not isinstance(
            self.sequence, int
        ):
            raise TypeError("sequence deve ser inteiro.")

        if self.sequence <= 0:
            raise ValueError("sequence deve ser maior que zero.")

        if not isinstance(self.rules, BusinessRules):
            raise TypeError("rules deve ser BusinessRules.")

        self.enqueued_at = self.order.arrival_time

        self.priority = self.rules.priority_for(
            self.order.channel,
            self.order.courier_waiting
        )

    def start_preparation(self, now: int) -> None:
        self._validate_time(now)

        if self.status != TicketStatus.WAITING:
            raise ValueError("O ticket não está aguardando.")

        if now < self.enqueued_at:
            raise ValueError("Início anterior à entrada na fila.")

        self.started_at = now
        self.status = TicketStatus.PREPARING

    def complete_preparation(self, now: int) -> None:
        self._validate_time(now)

        if self.status != TicketStatus.PREPARING:
            raise ValueError("O ticket não está em preparo.")

        if now < self.started_at:
            raise ValueError("Conclusão anterior ao início.")

        self.completed_at = now
        self.status = TicketStatus.COMPLETED

    def cancel(self) -> None:
        if self.status != TicketStatus.WAITING:
            raise ValueError(
                "Somente tickets aguardando podem ser cancelados."
            )

        self.status = TicketStatus.CANCELLED

    @staticmethod
    def _validate_time(now: int) -> None:
        if isinstance(now, bool) or not isinstance(now, int):
            raise TypeError("O horário deve ser inteiro.")

        if now < 0:
            raise ValueError("O horário não pode ser negativo.")