"""Fábrica, cenários reproduzíveis e indicadores usados pela interface."""

import random

from fastfood.audit.audit_logger import AuditLogger
from fastfood.domain.enums import OrderChannel, OrderComplexity
from fastfood.domain.order import Order
from fastfood.domain.rules import BusinessRules
from fastfood.queues.priority_policy import QuotaFairnessPolicy
from fastfood.queues.priority_queue import PriorityQueue
from fastfood.services.dispatcher import Dispatcher
from fastfood.services.simulation_engine import SimulationEngine
from fastfood.services.sla_monitor import SlaMonitor


def create_engine(rules=None, db_path=":memory:"):
    """Conecta os módulos das sete etapas sem dependência do Streamlit."""
    rules = rules or BusinessRules()
    queue = PriorityQueue()
    logger = AuditLogger(db_path)
    dispatcher = Dispatcher(
        queue, QuotaFairnessPolicy(rules), SlaMonitor(rules), logger
    )
    return SimulationEngine(dispatcher, queue, rules, logger)


def add_burst(engine, count=7, seed=42, urgent_percent=60, scenario="Aleatório"):
    """Cria lote determinístico, atômico, com IDs fictícios ainda não usados."""
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 200:
        raise ValueError("O lote deve ter entre 1 e 200 pedidos.")
    if not 0 <= urgent_percent <= 100:
        raise ValueError("Percentual deve estar entre 0 e 100.")
    rng = random.Random(seed)  # Gerador local: a mesma semente repete o perfil.
    with engine._atomic():
        for i in range(count):
            urgent = (
                i > 0
                if scenario == "Justiça 3:1"
                else rng.randrange(100) < urgent_percent
            )
            channel = (
                OrderChannel.DELIVERY
                if urgent
                else rng.choice([OrderChannel.COUNTER, OrderChannel.PICKUP])
            )
            complexity = (
                OrderComplexity.SIMPLE
                if scenario == "Justiça 3:1"
                else rng.choice(list(OrderComplexity))
            )
            number = engine._sequence_counter + 1
            while f"PED-{number:04}" in engine.tickets:
                number += 1
            engine.enqueue(
                Order(
                    f"PED-{number:04}", channel, complexity, engine.current_time, urgent
                )
            )
        engine.audit_logger.record_action(
            engine.current_time,
            "BURST",
            {
                "count": count,
                "seed": seed,
                "urgent_percent": urgent_percent,
                "scenario": scenario,
            },
        )


def metrics(engine):
    """Indicadores medidos dos inícios; cancelados não entram no denominador."""
    events = engine.audit_logger.fetch_all()
    started = [e for e in events if e["event_type"] == "SERVICE_STARTED"]
    waits = [e["wait_seconds"] for e in started]
    return {
        "started": len(started),
        "completed": sum(e["event_type"] == "PREPARATION_COMPLETED" for e in events),
        "compliance": 100
        * sum(e["sla_status"] == "MET" for e in started)
        / len(started)
        if started
        else None,
        "mean_wait": sum(waits) / len(waits) if waits else 0,
        "max_wait": max(waits, default=0),
    }
