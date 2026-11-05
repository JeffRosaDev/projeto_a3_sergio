from dataclasses import dataclass

from .enums import OrderChannel, OrderComplexity
from .rules import BusinessRules


@dataclass(frozen=True, slots=True)
class Order:
    id: str
    channel: OrderChannel
    complexity: OrderComplexity
    arrival_time: int
    courier_waiting: bool = False

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("O pedido precisa de um ID válido.")

        if isinstance(self.arrival_time, bool) or not isinstance(
            self.arrival_time, int
        ):
            raise TypeError("O horário deve ser um número inteiro.")

        if self.arrival_time < 0:
            raise ValueError("O horário não pode ser negativo.")

        if not isinstance(self.courier_waiting, bool):
            raise TypeError("courier_waiting deve ser booleano.")

        channel = BusinessRules._channel_value(self.channel)
        complexity = BusinessRules._complexity_value(self.complexity)

        object.__setattr__(self, "channel", channel)
        object.__setattr__(self, "complexity", complexity)