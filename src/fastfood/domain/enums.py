"""Enumerações compartilhadas entre o domínio, a fila e a auditoria."""

from enum import Enum, unique


@unique
class OrderChannel(str, Enum):
    """Canal de entrada de um pedido no cenário de fast food."""

    DELIVERY = "DELIVERY"
    PICKUP = "PICKUP"
    COUNTER = "COUNTER"


@unique
class OrderComplexity(str, Enum):
    """Faixa didática usada para estimar o tempo de preparo."""

    SIMPLE = "SIMPLE"
    MEDIUM = "MEDIUM"
    COMPLEX = "COMPLEX"


@unique
class TicketStatus(str, Enum):
    """Estado operacional do ticket dentro da estação de preparo."""

    WAITING = "WAITING"
    PREPARING = "PREPARING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


@unique
class PriorityLevel(str, Enum):
    """Faixa de prioridade imutável atribuída na entrada da fila."""

    URGENT = "URGENT"
    STANDARD = "STANDARD"


@unique
class SlaStatus(str, Enum):
    """Situação do tempo de espera diante da meta de SLA do canal."""

    WAITING = "WAITING"
    AT_RISK = "AT_RISK"
    MET = "MET"
    BREACHED = "BREACHED"


@unique
class QueueEventType(str, Enum):
    """Eventos que o motor emitirá para o módulo de auditoria."""

    ENQUEUED = "ENQUEUED"
    SERVICE_STARTED = "SERVICE_STARTED"
    PREPARATION_COMPLETED = "PREPARATION_COMPLETED"
    CANCELLED = "CANCELLED"
