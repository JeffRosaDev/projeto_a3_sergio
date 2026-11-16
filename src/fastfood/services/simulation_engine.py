"""Motor discreto de cozinha, regras dinâmicas e intervenções auditadas."""

from contextlib import contextmanager
from dataclasses import dataclass, fields
from uuid import uuid4

from fastfood.domain.enums import QueueEventType, TicketStatus
from fastfood.domain.events import QueueEvent
from fastfood.domain.order import Order
from fastfood.domain.rules import BusinessRules
from fastfood.domain.ticket import Ticket


@dataclass(frozen=True)
class SimulationSnapshot:
    """Visão de leitura do relógio, estação e filas agrupadas por faixa."""

    current_time: int
    preparing_ticket: Ticket | None
    queue_snapshot: list[Ticket]


class SimulationEngine:
    """Uma estação não preemptiva; alterações são atômicas com a auditoria."""

    def __init__(self, dispatcher, queue, rules, audit_logger):
        """Inicia uma sessão isolada e registra as hipóteses iniciais."""
        self.dispatcher, self.queue = dispatcher, queue
        self.rules, self.audit_logger = rules, audit_logger
        self.current_time = 0  # Segundos simulados desde o início da sessão.
        self.preparing_ticket = None  # No máximo um ticket em preparo.
        self.preparation_end_time = 0  # Prazo de conclusão do preparo corrente.
        self.station_paused = False  # Pausa da cozinha; relógio e espera continuam.
        self._sequence_counter = 0  # Desempate monotônico por chegada.
        self.tickets = {}  # IDs únicos em toda a sessão, incluindo concluídos.
        audit_logger.record_action(0, "CONFIG_INITIAL", rules.as_dict())

    @contextmanager
    def _atomic(self):
        """Faz rollback de memória e SQL conjuntamente, preservando referências."""
        clock = (
            self.current_time,
            self.preparing_ticket,
            self.preparation_end_time,
            self.station_paused,
            self._sequence_counter,
            self.rules,
        )
        tickets = self.tickets.copy()
        states = [
            (t, {f.name: getattr(t, f.name) for f in fields(t)})
            for t in tickets.values()
        ]
        queue = self.queue.snapshot()
        policy = self.dispatcher.policy.checkpoint()
        try:
            with self.audit_logger.transaction():
                yield
        except BaseException:
            (
                self.current_time,
                self.preparing_ticket,
                self.preparation_end_time,
                self.station_paused,
                self._sequence_counter,
                self.rules,
            ) = clock
            self.tickets = tickets
            for ticket, state in states:
                for name, value in state.items():
                    setattr(ticket, name, value)
            self.queue.restore(queue)
            self.dispatcher.policy.restore(policy)
            self.dispatcher.sla_monitor.rules = self.rules
            raise

    def enqueue(self, item: Order | Ticket) -> Ticket:
        """Admite apenas chegadas no segundo atual e IDs inéditos."""
        if not isinstance(item, (Order, Ticket)):
            raise TypeError("item deve ser Order ou Ticket.")
        order = item.order if isinstance(item, Ticket) else item
        if order.arrival_time != self.current_time:
            raise ValueError(
                "A chegada deve coincidir com o relógio atual; avance antes de inserir."
            )
        if order.id in self.tickets:
            raise ValueError("Esse ID já foi usado nesta sessão.")
        if len(self.queue.snapshot()) >= 2000:
            raise ValueError(
                "Limite de 2000 pedidos aguardando; avance ou cancele pedidos."
            )
        if isinstance(item, Ticket) and (
            item.status is not TicketStatus.WAITING
            or item.sequence <= self._sequence_counter
            or item.rules != self.rules
        ):
            raise ValueError(
                "Ticket precisa estar aguardando, com sequência nova e regras atuais."
            )
        with self._atomic():
            self._sequence_counter = (
                item.sequence
                if isinstance(item, Ticket)
                else self._sequence_counter + 1
            )
            ticket = (
                item
                if isinstance(item, Ticket)
                else Ticket(order, self._sequence_counter, self.rules)
            )
            before = len(self.queue.snapshot())
            self.queue.enqueue(ticket)
            self.tickets[ticket.id] = ticket
            self._event(ticket, QueueEventType.ENQUEUED, before)
            return ticket

    def _event(self, ticket, kind, before):
        """Monta evento completo após a mudança de estado."""
        after = self.queue.snapshot()
        started = ticket.started_at is not None
        monitor = self.dispatcher.sla_monitor
        self.audit_logger.record(
            QueueEvent(
                str(uuid4()),
                ticket.id,
                kind,
                self.current_time,
                ticket.order.channel,
                ticket.priority,
                before,
                len(after),
                tuple(t.id for t in after),
                monitor.wait_seconds(ticket, self.current_time) if started else None,
                ticket.rules.sla_seconds_for(ticket.order.channel),
                monitor.status(ticket, self.current_time) if started else None,
            )
        )

    def advance(self, seconds: int) -> SimulationSnapshot:
        """Avança até 86400 segundos por chamada; advance(0) só consulta."""
        Ticket._validate_time(seconds)
        if seconds > 86400:
            raise ValueError("Avance no máximo 86400 segundos por chamada.")
        if seconds == 0:
            return SimulationSnapshot(
                self.current_time, self.preparing_ticket, self.queue.snapshot()
            )
        with self._atomic():
            target = self.current_time + seconds
            while self.current_time < target:
                if self.station_paused:
                    if self.preparing_ticket:
                        self.preparation_end_time += target - self.current_time
                    self.current_time = target
                    break
                # Salta diretamente para conclusão ou início, sem laço por segundo vazio.
                self.current_time = (
                    min(target, self.preparation_end_time)
                    if self.preparing_ticket
                    else self.current_time + 1
                )
                if (
                    self.preparing_ticket
                    and self.current_time >= self.preparation_end_time
                ):
                    ticket = self.preparing_ticket
                    ticket.complete_preparation(self.current_time)
                    self._event(
                        ticket,
                        QueueEventType.PREPARATION_COMPLETED,
                        len(self.queue.snapshot()),
                    )
                    self.preparing_ticket = None
                if self.preparing_ticket is None:
                    self.preparing_ticket = self.dispatcher.start_next(
                        self.current_time
                    )
                    if self.preparing_ticket:
                        duration = self.rules.preparation_seconds_for(
                            self.preparing_ticket.order.complexity
                        )
                        self.preparation_end_time = self.current_time + duration
                    elif not self.queue.snapshot():
                        self.current_time = target
            return SimulationSnapshot(
                self.current_time, self.preparing_ticket, self.queue.snapshot()
            )

    def configure(self, rules: BusinessRules):
        """SLA/prioridade valem para novas chegadas; preparo para próximos inícios."""
        if not isinstance(rules, BusinessRules):
            raise TypeError("rules deve ser BusinessRules.")
        with self._atomic():
            self.audit_logger.record_action(
                self.current_time, "CONFIG_CHANGED", rules.as_dict()
            )
            self.rules = rules
            self.dispatcher.sla_monitor.rules = rules
            self.dispatcher.policy.configure(rules)

    def pause_station(self, paused: bool):
        """Simula indisponibilidade física: o relógio segue e a produção para."""
        if not isinstance(paused, bool):
            raise TypeError("paused deve ser bool.")
        with self._atomic():
            self.audit_logger.record_action(
                self.current_time, "STATION_PAUSE" if paused else "STATION_RESUME", {}
            )
            self.station_paused = paused

    def adjust_remaining(self, seconds: int):
        """Redefine explicitamente o tempo restante por incidente ou recuperação."""
        Ticket._validate_time(seconds)
        if not 1 <= seconds <= 86400 or self.preparing_ticket is None:
            raise ValueError(
                "É necessário um preparo ativo e tempo restante entre 1 e 86400 s."
            )
        with self._atomic():
            self.audit_logger.record_action(
                self.current_time,
                "PREPARATION_ADJUSTED",
                {
                    "ticket_id": self.preparing_ticket.id,
                    "remaining_before": self.preparation_end_time - self.current_time,
                    "remaining_after": seconds,
                },
            )
            self.preparation_end_time = self.current_time + seconds

    def cancel(self, ticket_id: str):
        """Cancela pedido em espera e registra a remoção, sem apagar histórico."""
        ticket = self.tickets.get(ticket_id)
        if ticket is None or ticket.status is not TicketStatus.WAITING:
            raise ValueError("Somente pedido em espera pode ser cancelado.")
        with self._atomic():
            before = len(self.queue.snapshot())
            ticket.cancel()
            self.queue.remove(ticket)
            self._event(ticket, QueueEventType.CANCELLED, before)
