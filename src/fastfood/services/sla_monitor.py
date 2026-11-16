"""Cálculo de espera com SLA congelado na entrada do ticket."""

from fastfood.domain.enums import SlaStatus
from fastfood.domain.rules import BusinessRules
from fastfood.domain.ticket import Ticket


class SlaMonitor:
    """Consulta a configuração de cada ticket, preservando metas históricas."""

    def __init__(self, business_rules=None):
        """Configuração corrente serve para novos tickets e limiar de alerta."""
        self.rules = business_rules or BusinessRules()

    def wait_seconds(self, ticket, now: int) -> int:
        """Congela a espera no início, incluindo corretamente início em zero."""
        Ticket._validate_time(now)
        if now < ticket.enqueued_at:
            raise ValueError("Consulta anterior à chegada.")
        return (
            ticket.started_at if ticket.started_at is not None else now
        ) - ticket.enqueued_at

    def status(self, ticket, now: int) -> SlaStatus:
        """O limite pertence ao ticket; o alerta usa a fração corrente."""
        wait = self.wait_seconds(ticket, now)
        limit = ticket.rules.sla_seconds_for(ticket.order.channel)
        if ticket.started_at is not None:
            return SlaStatus.MET if wait <= limit else SlaStatus.BREACHED
        if wait > limit:
            return SlaStatus.BREACHED
        if wait >= limit * self.rules.at_risk_fraction:
            return SlaStatus.AT_RISK
        return SlaStatus.WAITING
