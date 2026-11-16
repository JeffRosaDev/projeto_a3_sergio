"""KitchenFlow: painel da cozinha, laboratório de cenários e auditoria da Etapa 7.

Derivado da interface fornecida pelo integrante; regras e transações residem no
núcleo fastfood. HTML recebe somente textos escapados, nunca código do usuário.
"""

import sqlite3
import time
from html import escape
from pathlib import Path
from uuid import uuid4

import streamlit as st

from fastfood.domain.enums import (
    OrderChannel,
    OrderComplexity,
    PriorityLevel,
)
from fastfood.domain.order import Order
from fastfood.domain.rules import BusinessRules
from fastfood.services.scenarios import add_burst, create_engine, metrics

# Vocabulário de apresentação; valores internos continuam sendo enums compartilhados.
CHANNELS = {
    "Delivery": OrderChannel.DELIVERY,
    "Retirada": OrderChannel.PICKUP,
    "Balcão": OrderChannel.COUNTER,
}
COMPLEXITIES = {
    "Simples": OrderComplexity.SIMPLE,
    "Médio": OrderComplexity.MEDIUM,
    "Complexo": OrderComplexity.COMPLEX,
}
SLA_LABELS = {
    "WAITING": "No prazo",
    "AT_RISK": "Em risco",
    "MET": "Cumpriu",
    "BREACHED": "Excedeu",
}
ROOT = (
    Path(__file__).resolve().parent
)  # Resolve recursos independentemente do diretório de execução.


def act(callback, message):
    """Executa ação de usuário e apresenta erros esperados sem quebrar a sessão."""
    try:
        callback()
        st.success(message)
    except (ValueError, TypeError, sqlite3.Error, OSError) as error:
        st.error(f"Não foi possível: {error}")


def init_session():
    """Cria banco exclusivo em disco e preserva o motor entre atualizações."""
    if "engine" not in st.session_state:
        directory = ROOT / "data"
        directory.mkdir(exist_ok=True)
        st.session_state.engine = create_engine(
            db_path=directory / f"{uuid4().hex}.sqlite3"
        )
        st.session_state.auto = False
        st.session_state.last_tick = time.monotonic()
        st.session_state.burst_tick = 0


def ticket_card(ticket, engine):
    """Exibe espera, meta contratada e risco por texto e cor em cartão escapado."""
    monitor = engine.dispatcher.sla_monitor
    wait = monitor.wait_seconds(ticket, engine.current_time)
    target = ticket.rules.sla_seconds_for(ticket.order.channel)
    status = monitor.status(ticket, engine.current_time).value
    color = {"BREACHED": "#b42318", "AT_RISK": "#9a6700"}.get(status, "#26765b")
    channel = next(k for k, v in CHANNELS.items() if v == ticket.order.channel)
    st.markdown(
        f"""<div class="ticket" style="border-left-color:{color}">
        <div class="ticket-top"><b>{escape(ticket.id)}</b><span style="color:{color}">{SLA_LABELS[status]}</span></div>
        <p>{channel} · {ticket.order.complexity.value.lower()}</p>
        <div class="ticket-top"><strong>{wait}s de espera</strong><span>meta {target}s</span></div>
        <div class="wait-track"><i style="width:{min(100, 100 * wait / target)}%;background:{color}"></i></div></div>""",
        unsafe_allow_html=True,
    )


def laboratory(engine):
    """Editor explícito de hipóteses com aplicação auditada e efeitos documentados."""
    st.subheader("Configure a próxima decisão")
    st.caption(
        "SLA e prioridade valem para novos pedidos. Tempos de preparo valem para próximos inícios. Cota e alerta mudam imediatamente; o contador da cota é preservado."
    )
    rules = engine.rules
    with st.form("rules"):
        left, right = st.columns(2)
        with left:
            st.markdown("**Metas para iniciar o preparo · segundos**")
            sla = {
                v: st.number_input(
                    k,
                    min_value=1,
                    max_value=86400,
                    value=rules.sla_seconds_for(v),
                    key=f"sla_{v.value}",
                )
                for k, v in CHANNELS.items()
            }
        with right:
            st.markdown("**Duração de preparo · segundos**")
            prep = {
                v: st.number_input(
                    k,
                    min_value=1,
                    max_value=86400,
                    value=rules.preparation_seconds_for(v),
                    key=f"prep_{v.value}",
                )
                for k, v in COMPLEXITIES.items()
            }
        a, b = st.columns(2)
        quota = a.number_input(
            "Máximo de urgentes consecutivos", 1, 50, rules.urgent_quota, key="quota"
        )
        risk = b.slider(
            "Alerta ao consumir (%) do SLA",
            1,
            100,
            int(rules.at_risk_fraction * 100),
            key="risk",
        )
        urgent = st.checkbox(
            "Priorizar novos deliveries com entregador aguardando",
            value=rules.prioritize_delivery,
            key="priority_on",
        )
        if st.form_submit_button("Aplicar parâmetros", type="primary"):
            act(
                lambda: engine.configure(
                    BusinessRules(sla, prep, urgent, quota, risk / 100)
                ),
                "Parâmetros aplicados e registrados.",
            )
    st.subheader("Imprevistos da cozinha")
    a, b = st.columns(2)
    if a.button(
        "Retomar cozinha" if engine.station_paused else "Pausar cozinha",
        key="pause_station",
    ):
        act(
            lambda: engine.pause_station(not engine.station_paused),
            "Estado da cozinha registrado.",
        )
        st.rerun()
    b.caption(
        "A pausa da cozinha mantém o relógio correndo. Pedidos aguardam e podem exceder o SLA. O preparo em andamento fica suspenso."
    )
    with st.form("remaining"):
        remaining = st.number_input(
            "Novo tempo restante do preparo atual (s)", 1, 86400, 60, key="remaining"
        )
        if st.form_submit_button(
            "Ajustar preparo atual", disabled=engine.preparing_ticket is None
        ):
            act(
                lambda: engine.adjust_remaining(remaining),
                "Tempo restante ajustado e auditado.",
            )
    waiting = [t.id for t in engine.queue.snapshot()]
    if waiting:
        cancel = st.selectbox(
            "Pedido aguardando para cancelar", waiting, key="cancel_id"
        )
        if st.button("Cancelar pedido", key="cancel"):
            act(lambda: engine.cancel(cancel), "Cancelamento registrado.")
            st.rerun()


def history(engine):
    """Downloads completos e histórico filtrável, sem sobrescrever dados de outras sessões."""
    logger = engine.audit_logger
    st.subheader("Cada decisão deixa uma trilha")
    st.caption(
        "Banco exclusivo desta sessão. Entradas, inícios, conclusões, cancelamentos e mudanças de configuração ficam registrados. SQL inclui schema e dados; importe em banco vazio."
    )
    a, b = st.columns(2)
    a.download_button(
        "Baixar histórico completo · SQL",
        logger.export_sql(),
        "logs.sql",
        "application/sql",
        key="download_sql",
    )
    b.download_button(
        "Baixar estrutura · SQL",
        (ROOT / "sql/schema.sql").read_text(encoding="utf-8"),
        "schema.sql",
        "application/sql",
        key="download_schema",
    )
    filter_type = st.selectbox(
        "Tipo de evento",
        ["Todos", "ENQUEUED", "SERVICE_STARTED", "PREPARATION_COMPLETED", "CANCELLED"],
        key="event_filter",
    )
    rows = logger.fetch_all()
    if filter_type != "Todos":
        rows = [r for r in rows if r["event_type"] == filter_type]
    st.dataframe(rows[-300:], hide_index=True, width="stretch")
    st.caption(
        "A tela mostra até 300 eventos recentes; o download contém todo o histórico."
    )
    with st.expander("Alterações de regras e incidentes"):
        st.dataframe(logger.actions(), hide_index=True, width="stretch")


def dashboard(engine):
    """Painel operacional com progresso calculado pelo relógio simulado."""
    m = metrics(engine)
    cols = st.columns(4)
    cols[0].metric(
        "RELÓGIO SIMULADO",
        f"{engine.current_time // 60:02}:{engine.current_time % 60:02}",
    )
    cols[1].metric("NA FILA", len(engine.queue.snapshot()))
    cols[2].metric("FINALIZADOS", m["completed"])
    cols[3].metric(
        "INÍCIOS NO SLA", "—" if m["compliance"] is None else f"{m['compliance']:.1f}%"
    )
    st.caption(
        f"Espera média dos iniciados: {m['mean_wait']:.1f}s · Maior espera: {m['max_wait']}s · {m['started']} pedidos iniciados"
    )
    with st.expander("Espera e SLA por canal"):
        events = [
            e
            for e in engine.audit_logger.fetch_all()
            if e["event_type"] == "SERVICE_STARTED"
        ]
        per_channel = []  # Agregados medidos; canais sem início não têm percentual.
        for label, channel in CHANNELS.items():
            rows = [e for e in events if e["channel"] == channel.value]
            per_channel.append(
                {
                    "Canal": label,
                    "Iniciados": len(rows),
                    "Espera média (s)": round(
                        sum(e["wait_seconds"] for e in rows) / len(rows), 1
                    )
                    if rows
                    else None,
                    "Maior espera (s)": max(
                        (e["wait_seconds"] for e in rows), default=0
                    ),
                    "SLA cumprido (%)": round(
                        100 * sum(e["sla_status"] == "MET" for e in rows) / len(rows), 1
                    )
                    if rows
                    else None,
                }
            )
        st.dataframe(per_channel, hide_index=True, width="stretch")
    cooking = engine.preparing_ticket
    with st.container(border=True):
        st.subheader(
            "Estação 01 · "
            + (
                "Suspensa"
                if engine.station_paused
                else "Em preparo"
                if cooking
                else "Disponível"
            )
        )
        if cooking:
            remaining = engine.preparation_end_time - engine.current_time
            duration = engine.preparation_end_time - cooking.started_at
            st.markdown(
                f"**{escape(cooking.id)}** · faltam **{remaining}s** · previsão no segundo **{engine.preparation_end_time}**"
            )
            st.progress(
                min(1.0, max(0.0, 1 - remaining / duration)),
                text="Preparo suspenso"
                if engine.station_paused
                else "Pedido em produção",
            )
            st.caption(
                "A barra acompanha o prazo atual; uma intervenção pode alterar essa previsão."
            )
        else:
            st.info(
                "Registre pedidos e avance o relógio para iniciar o preparo."
                if not engine.queue.snapshot()
                else "Há pedidos prontos para começar. Avance o relógio."
            )
    chosen = engine.dispatcher.policy.choose_priority(engine.queue)
    chosen_text = (
        "Urgente"
        if chosen is PriorityLevel.URGENT
        else "Padrão"
        if chosen
        else "Nenhuma"
    )
    st.markdown(
        f"**Próxima faixa elegível: {chosen_text}** · urgentes consecutivos: {engine.dispatcher.policy.consecutive_urgent_starts}/{engine.rules.urgent_quota}"
    )
    a, b = st.columns(2)
    for column, priority, label in [
        (a, PriorityLevel.URGENT, "Urgentes"),
        (b, PriorityLevel.STANDARD, "Padrão"),
    ]:
        with column:
            tickets = [t for t in engine.queue.snapshot() if t.priority is priority]
            st.markdown(
                f'### {label} <span class="count">{len(tickets)}</span>',
                unsafe_allow_html=True,
            )
            if not tickets:
                st.caption("Faixa livre. Novos pedidos aparecerão aqui.")
            for ticket in tickets[:12]:
                ticket_card(ticket, engine)
            if len(tickets) > 12:
                st.caption(f"Mais {len(tickets) - 12} pedidos nesta faixa.")
    with st.expander("Todos os pedidos e seus estados"):
        st.dataframe(
            [
                {
                    "Pedido": t.id,
                    "Estado": t.status.value,
                    "Prioridade": t.priority.value,
                    "Chegada": t.enqueued_at,
                    "Início": t.started_at,
                    "Conclusão": t.completed_at,
                    "Meta SLA": t.rules.sla_seconds_for(t.order.channel),
                }
                for t in engine.tickets.values()
            ],
            hide_index=True,
            width="stretch",
        )


def main():
    """Inicializa a página e os comandos; só a área viva avança automaticamente."""
    st.set_page_config(
        page_title="KitchenFlow · Cozinha em movimento", page_icon="🍔", layout="wide"
    )
    if st.session_state.pop("stop_requested", False):
        st.session_state.auto = False
    # O erro sobrevive ao rerun que desliga a reprodução, para explicar a parada.
    automation_error = st.session_state.pop("automation_error", None)
    init_session()
    engine = st.session_state.engine
    st.markdown(
        "<style>"
        + (ROOT / "assets/style.css").read_text(encoding="utf-8")
        + "</style>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="eyebrow">KITCHENFLOW / LABORATÓRIO DE OPERAÇÕES</div><h1>Uma cozinha. Cada segundo conta.</h1><p class="lead">Experimente o movimento, acompanhe a fila e entenda cada decisão.</p>',
        unsafe_allow_html=True,
    )
    if automation_error:
        st.error(automation_error)
    with st.sidebar:
        st.markdown("## 🍔 KitchenFlow")
        st.caption("SIMULAÇÃO ACADÊMICA · PROJETO A3")
        with st.form("new_order", clear_on_submit=True):
            st.subheader("Novo pedido")
            order_id = st.text_input(
                "Identificador (opcional)", max_chars=64, key="order_id"
            )
            channel = st.selectbox("Canal", list(CHANNELS), key="channel")
            complexity = st.selectbox(
                "Complexidade", list(COMPLEXITIES), key="complexity"
            )
            courier = st.checkbox("Entregador já aguarda", key="courier")
            if st.form_submit_button(
                "Adicionar à fila", type="primary", width="stretch"
            ):

                def enqueue():
                    """Gera ID único quando vazio e usa o horário real do motor."""
                    identifier = order_id.strip() or "PED-" + uuid4().hex[:6].upper()
                    engine.enqueue(
                        Order(
                            identifier,
                            CHANNELS[channel],
                            COMPLEXITIES[complexity],
                            engine.current_time,
                            courier and channel == "Delivery",
                        )
                    )

                act(enqueue, "Pedido adicionado à fila.")
        st.divider()
        st.subheader("Controle do tempo")
        c1, c2 = st.columns(2)
        if c1.button("+1 segundo", key="step1"):
            act(lambda: engine.advance(1), "Relógio avançado.")
        if c2.button("+60 segundos", key="step60"):
            act(lambda: engine.advance(60), "Relógio avançado.")
        seconds = st.number_input(
            "Avanço manual (s)", 1, 86400, 180, key="manual_seconds"
        )
        if st.button("Avançar", key="advance"):
            act(lambda: engine.advance(seconds), "Relógio avançado.")
        st.toggle("Reprodução automática", key="auto")
        st.select_slider(
            "Segundos simulados por atualização",
            options=[1, 5, 15, 30, 60],
            value=5,
            key="speed",
        )
        st.checkbox("Chegadas durante reprodução", key="arrivals")
        st.number_input(
            "Intervalo entre chegadas (s simulados)",
            1,
            3600,
            30,
            key="arrival_interval",
        )
        st.caption(
            "Reprodução avança enquanto a página está aberta. Pausá-la congela o relógio; pausar a cozinha mantém a espera crescendo."
        )
        st.divider()
        st.subheader("Cenários")
        scenario = st.selectbox("Perfil", ["Justiça 3:1", "Aleatório"], key="scenario")
        count = st.number_input("Pedidos no lote", 1, 200, 7, key="count")
        seed = st.number_input("Semente reproduzível", 0, 999999, 42, key="seed")
        percent = st.slider("Deliveries urgentes (%)", 0, 100, 60, key="percent")
        if st.button("Adicionar cenário", key="burst"):
            act(
                lambda: add_burst(engine, count, seed, percent, scenario),
                "Lote inserido. Justiça usa 1 padrão e os demais urgentes; confira a cota atual.",
            )
        with st.expander("Nova sessão"):
            st.caption(
                "O banco anterior permanece em data/. Baixe o SQL antes de iniciar outra sessão."
            )
            confirm = st.checkbox("Confirmo iniciar outra sessão", key="reset_confirm")

            def reset_session():
                """Callback anterior aos widgets; preserva o banco e limpa parâmetros visuais."""
                engine.audit_logger.close()
                for key in list(st.session_state):
                    if key != "reset":
                        del st.session_state[key]

            st.button(
                "Iniciar nova sessão",
                disabled=not confirm,
                key="reset",
                on_click=reset_session,
            )

    @st.fragment(run_every=1)
    def live():
        """Atualiza a tela; chegadas são intercaladas a cada segundo simulado."""
        now = time.monotonic()
        if st.session_state.auto and now - st.session_state.last_tick >= 0.9:
            try:
                for _ in range(st.session_state.speed):
                    engine.advance(1)
                    if (
                        st.session_state.arrivals
                        and engine.current_time % st.session_state.arrival_interval == 0
                    ):
                        add_burst(
                            engine,
                            1,
                            st.session_state.seed + engine.current_time,
                            st.session_state.percent,
                            "Aleatório",
                        )
            except (ValueError, TypeError, sqlite3.Error) as error:
                st.session_state.stop_requested = True
                st.session_state.automation_error = f"Reprodução interrompida: {error}"
                st.rerun()
        st.session_state.last_tick = now
        operation, lab, audit, guide = st.tabs(
            ["Operação ao vivo", "Laboratório", "Histórico", "Como demonstrar"]
        )
        with operation:
            dashboard(engine)
        with lab:
            laboratory(engine)
        with audit:
            history(engine)
        with guide:
            st.markdown(
                """### Do pico à decisão\n1. Carregue **Justiça 3:1** em sessão vazia com regras padrão.\n2. Avance **1s** e depois **60s** três vezes: o padrão começa no segundo 181.\n3. No laboratório, aumente os preparos e adicione novos pedidos. Observe a espera.\n4. Pause a cozinha, avance o relógio e acompanhe os SLAs excedidos.\n5. Retome, cancele um pedido em espera e exporte o histórico SQL.\n\n**SLA = início do preparo − entrada na fila.** A cota protege oportunidades de atendimento; não aumenta a capacidade da cozinha. Uma sobrecarga pode violar SLAs.\n\nAs metas, durações e urgência são hipóteses didáticas configuráveis. Uma estação, sem interrupção para trocar de pedido. POO, FIFO, política por cota e SQLite sustentam a interface."""
            )

    live()


if __name__ == "__main__":
    main()
