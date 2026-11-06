"""Parâmetros e regras puras da simulação, sem acesso a UI ou banco de dados."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TypeVar

from .enums import OrderChannel, OrderComplexity, PriorityLevel

EnumKey = TypeVar("EnumKey", OrderChannel, OrderComplexity)


def _validated_map(
    values: Mapping[EnumKey, int],
    expected_keys: set[EnumKey],
    name: str,
) -> Mapping[EnumKey, int]:
    """Copia um mapa de configuração, valida as chaves/valores e o torna somente leitura."""

    if not isinstance(values, Mapping):
        raise TypeError(f"{name} deve ser um mapeamento.")

    actual_keys = set(values)
    if actual_keys != expected_keys:
        missing = expected_keys - actual_keys
        unexpected = actual_keys - expected_keys
        details: list[str] = []
        if missing:
            details.append(f"chaves ausentes: {sorted(key.value for key in missing)}")
        if unexpected:
            details.append("há chaves que não pertencem à enumeração esperada")
        raise ValueError(f"{name} inválido ({'; '.join(details)}).")

    copied: dict[EnumKey, int] = {}
    for key, seconds in values.items():
        if isinstance(seconds, bool) or not isinstance(seconds, int):
            raise TypeError(f"Os valores de {name} devem ser inteiros em segundos.")
        if seconds <= 0:
            raise ValueError(f"Os valores de {name} devem ser maiores que zero.")
        copied[key] = seconds

    # A cópia evita que a pessoa que passou o dicionário altere as regras depois.
    return MappingProxyType(copied)


@dataclass(frozen=True, slots=True)
class BusinessRules:
    """Configuração imutável para classificar pedidos e consultar parâmetros.

    Os valores padrão são hipóteses didáticas e podem ser substituídos para
    experimentar outros cenários sem mudar a lógica do domínio.
    """

    sla_targets_seconds: Mapping[OrderChannel, int] = field(
        default_factory=lambda: {
            OrderChannel.DELIVERY: 180,
            OrderChannel.PICKUP: 300,
            OrderChannel.COUNTER: 480,
        }
    )
    preparation_times_seconds: Mapping[OrderComplexity, int] = field(
        default_factory=lambda: {
            OrderComplexity.SIMPLE: 60,
            OrderComplexity.MEDIUM: 120,
            OrderComplexity.COMPLEX: 180,
        }
    )
    urgent_quota: int = 3
    at_risk_fraction: float = 0.8

    def __post_init__(self) -> None:
        """Valida a configuração e congela os mapas internos da instância."""

        sla_targets = _validated_map(
            self.sla_targets_seconds,
            set(OrderChannel),
            "sla_targets_seconds",
        )
        preparation_times = _validated_map(
            self.preparation_times_seconds,
            set(OrderComplexity),
            "preparation_times_seconds",
        )
        object.__setattr__(self, "sla_targets_seconds", sla_targets)
        object.__setattr__(self, "preparation_times_seconds", preparation_times)

        if isinstance(self.urgent_quota, bool) or not isinstance(self.urgent_quota, int):
            raise TypeError("urgent_quota deve ser um inteiro.")
        if self.urgent_quota <= 0:
            raise ValueError("urgent_quota deve ser maior que zero.")

        if isinstance(self.at_risk_fraction, bool) or not isinstance(
            self.at_risk_fraction, (int, float)
        ):
            raise TypeError("at_risk_fraction deve ser numérico.")
        if not 0 < self.at_risk_fraction <= 1:
            raise ValueError("at_risk_fraction deve estar no intervalo (0, 1].")

    def priority_for(
        self,
        channel: OrderChannel | str,
        courier_waiting: bool,
    ) -> PriorityLevel:
        """Calcula a prioridade de valores simples, sem receber um objeto Order."""

        if not isinstance(courier_waiting, bool):
            raise TypeError("courier_waiting deve ser bool.")
        channel_value = self._channel_value(channel)

        # A urgência existe somente quando um entregador de delivery já aguarda.
        if channel_value is OrderChannel.DELIVERY and courier_waiting:
            return PriorityLevel.URGENT
        return PriorityLevel.STANDARD

    def sla_seconds_for(self, channel: OrderChannel | str) -> int:
        """Devolve o SLA do canal, aceitando enum ou texto como valor simples."""

        return self.sla_targets_seconds[self._channel_value(channel)]

    def preparation_seconds_for(self, complexity: OrderComplexity | str) -> int:
        """Devolve o preparo da complexidade, aceitando enum ou texto simples."""

        return self.preparation_times_seconds[self._complexity_value(complexity)]

    @staticmethod
    def _channel_value(channel: OrderChannel | str) -> OrderChannel:
        """Normaliza um canal textual para o enum usado internamente."""

        if isinstance(channel, OrderChannel):
            return channel
        if not isinstance(channel, str):
            raise TypeError("channel deve ser texto ou OrderChannel.")
        try:
            # A normalização aceita valores simples como "delivery" e " DELIVERY ".
            return OrderChannel(channel.strip().upper())
        except ValueError as error:
            raise ValueError(f"Canal desconhecido: {channel!r}.") from error

    @staticmethod
    def _complexity_value(complexity: OrderComplexity | str) -> OrderComplexity:
        """Normaliza uma complexidade textual para o enum interno."""

        if isinstance(complexity, OrderComplexity):
            return complexity
        if not isinstance(complexity, str):
            raise TypeError("complexity deve ser texto ou OrderComplexity.")
        try:
            # Usar texto simples mantém as regras desacopladas da classe Order.
            return OrderComplexity(complexity.strip().upper())
        except ValueError as error:
            raise ValueError(f"Complexidade desconhecida: {complexity!r}.") from error
