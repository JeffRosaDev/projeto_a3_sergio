# src/fastfood/services/sla_monitor.py

from fastfood.domain.enums import SlaStatus, TicketStatus

class SlaMonitor:
    def __init__(self, business_rules):
        self.rules = business_rules

    def wait_seconds(self, ticket, now: int) -> int:
        """
        Calcula o tempo de espera.
        A espera é o horário de início (se já começou) ou o horário atual (now)
        menos o horário de entrada na fila.
        """
        # Se o preparo já iniciou, a espera congela no start_time.
        # Caso contrário, continua contando até o 'now' simulado.
        end_time = ticket.start_time if ticket.start_time is not None else now
        return end_time - ticket.arrival_time

    def status(self, ticket, now: int) -> SlaStatus:
        """
        Classifica o cumprimento da meta de SLA.
        """
        wait = self.wait_seconds(ticket, now)
        limit = self.rules.sla_seconds_for(ticket.order.channel)

        # Se o pedido já saiu da fila (já começou a ser preparado ou terminou)
        if ticket.status in (TicketStatus.PREPARING, TicketStatus.COMPLETED):
            return SlaStatus.MET if wait <= limit else SlaStatus.BREACHED

        # Se o pedido ainda está esperando na fila
        if wait > limit:
            return SlaStatus.BREACHED
        
        # Fica EM_RISCO quando consome 80% ou mais do tempo limite estipulado
        if wait >= limit * 0.8:
            return SlaStatus.AT_RISK
            
        return SlaStatus.WAITING