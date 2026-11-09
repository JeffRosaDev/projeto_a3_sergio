"""Monitoramento de SLA e cálculo de tempo de espera."""

from fastfood.domain.enums import SlaStatus, TicketStatus
from fastfood.domain.rules import BusinessRules


class SlaMonitor:
    """Calcula o tempo de espera e avalia o cumprimento de SLA dos tickets."""

    def __init__(self, business_rules: BusinessRules | None = None) -> None:
        self.rules = business_rules if business_rules is not None else BusinessRules()

    def wait_seconds(self, ticket, now: int) -> int:
        """Calcula a espera decorrida ou final até o início do preparo.

        espera = horário_de_início_do_preparo - horário_de_entrada_na_fila
        Se o preparo já começou, a espera congela no instante de início.
        """
        start_time = getattr(ticket, "started_at", None)
        if start_time is None:
            start_time = getattr(ticket, "start_time", None)

        enqueued_time = getattr(
            ticket, "enqueued_at", getattr(ticket.order, "arrival_time", 0)
        )

        end_time = start_time if start_time is not None else now
        return max(0, end_time - enqueued_time)

    def status(self, ticket, now: int) -> SlaStatus:
        """Classifica o cumprimento do SLA conforme a meta do canal e a espera."""
        wait = self.wait_seconds(ticket, now)
        limit = self.rules.sla_seconds_for(ticket.order.channel)
        risk_limit = limit * self.rules.at_risk_fraction

        if ticket.status in (TicketStatus.PREPARING, TicketStatus.COMPLETED):
            return SlaStatus.MET if wait <= limit else SlaStatus.BREACHED

        if wait > limit:
            return SlaStatus.BREACHED

        if wait >= risk_limit:
            return SlaStatus.AT_RISK

        return SlaStatus.WAITING
