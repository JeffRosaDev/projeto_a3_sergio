"""KitchenFlow: painel da cozinha, laboratório de cenários e auditoria da Etapa 7.

Derivado da interface fornecida pelo integrante; regras e transações residem no
núcleo fastfood. HTML recebe somente textos escapados, nunca código do usuário.
"""

import sqlite3
import json
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
from fastfood.services.playback import PlaybackClock, advance_playback

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
    """Executa um comando; mantém o resultado visível mesmo após um rerun."""
    try:
        callback()
        st.session_state.notice = ("success", message)
        return True
    except (ValueError, TypeError, sqlite3.Error, OSError) as error:
        st.session_state.notice = ("error", f"Não foi possível: {error}")
        return False


def init_session():
    """Cria banco exclusivo em disco e preserva o motor entre atualizações."""
    if "engine" not in st.session_state:
        directory = ROOT / "data"
        directory.mkdir(exist_ok=True)
        st.session_state.engine = create_engine(
            db_path=directory / f"{uuid4().hex}.sqlite3"
        )
        st.session_state.auto = False
    if "playback_clock" not in st.session_state:
        st.session_state.playback_clock = PlaybackClock()


def reset_clock():
    """Descarta tempo pausado e começa a medir a configuração recém-aplicada."""
    st.session_state.playback_clock.reset(time.monotonic())


def toggle_playback():
    """Inicia/pausa o temporizador por ação explícita no controle principal."""
    running = not st.session_state.auto
    engine = st.session_state.engine
    if not act(
        lambda: engine.audit_logger.record_action(
            engine.current_time,
            "PLAYBACK_STARTED" if running else "PLAYBACK_PAUSED",
            {"speed": st.session_state.speed},
        ),
        "Reprodução iniciada." if running else "Reprodução pausada.",
    ):
        return
    st.session_state.auto = running
    reset_clock()


def manual_advance(engine, seconds):
    """Registra o comando manual e seus limites na mesma transação do avanço."""
    with engine._atomic():
        before = engine.current_time
        engine.advance(seconds)
        engine.audit_logger.record_action(
            engine.current_time,
            "TIME_ADVANCED",
            {"from": before, "to": engine.current_time},
        )


def submit_order():
    """Admite um pedido; só limpa seu ID quando a operação realmente funciona."""
    state = st.session_state
    identifier = state.order_id.strip() or "PED-" + uuid4().hex[:6].upper()
    if act(
        lambda: state.engine.enqueue(
            Order(
                identifier,
                CHANNELS[state.channel],
                COMPLEXITIES[state.complexity],
                state.engine.current_time,
                state.courier and state.channel == "Delivery",
            )
        ),
        "Pedido adicionado. Use Iniciar simulação ou avance manualmente.",
    ):
        state.order_id = ""


def reset_session():
    """Fecha o banco atual sem apagá-lo e prepara uma nova simulação isolada."""
    st.session_state.engine.audit_logger.close()
    for key in list(st.session_state):
        if key != "reset":
            del st.session_state[key]


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
        <p>{channel} · {next(k for k, v in COMPLEXITIES.items() if v == ticket.order.complexity)}</p>
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
            st.rerun()
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
        if st.form_submit_button("Ajustar preparo atual"):
            act(
                lambda: engine.adjust_remaining(remaining),
                "Tempo restante ajustado e auditado.",
            )
            st.rerun()
    st.caption("Informe o novo restante e aplique quando houver pedido em preparo.")
    st.button("Atualizar pedidos para cancelamento", key="refresh_waiting")
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
        "Auditoria desta sessão: eventos do motor e comandos do operador. Não há identificação pessoal ou histórico compartilhado entre visitantes. Horário real em UTC."
    )
    st.button("Atualizar histórico", key="refresh_history")
    st.caption(
        f"Consulta no segundo {engine.current_time}. Atualize para incluir novas decisões ou pause a simulação antes de exportar."
    )
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
        on_click="ignore",
    )
    b.download_button(
        "Baixar estrutura · SQL",
        (ROOT / "sql/schema.sql").read_text(encoding="utf-8"),
        "schema.sql",
        "application/sql",
        key="download_schema",
        on_click="ignore",
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
    st.subheader("Trilha completa em ordem de registro")
    timeline = logger.timeline()
    kinds = st.multiselect(
        "Operações na auditoria",
        sorted({r["operation"] for r in timeline}),
        key="log_operations",
    )
    search = st.text_input(
        "Buscar ID ou detalhe",
        key="log_search",
        placeholder="Ex.: PED-0001, remaining_after",
    )
    filtered = [
        row
        for row in timeline
        if (not kinds or row["operation"] in kinds)
        and (
            not search
            or search.casefold() in json.dumps(row, ensure_ascii=False).casefold()
        )
    ]
    st.caption(
        f"{len(filtered)} de {len(timeline)} registros. A tabela mostra os últimos 500; a exportação inclui todos os filtrados."
    )
    st.dataframe(filtered[-500:], hide_index=True, width="stretch")
    st.download_button(
        "Exportar auditoria filtrada · JSON",
        json.dumps(filtered, ensure_ascii=False, indent=2),
        "auditoria.json",
        "application/json",
        on_click="ignore",
        key="download_audit",
    )


def dashboard(engine):
    """Painel operacional com progresso calculado pelo relógio simulado."""
    m = metrics(engine)
    mode = "Em andamento" if st.session_state.auto else "Relógio pausado"
    st.markdown(
        f'<div class="live-status"><span class="status-dot {"running" if st.session_state.auto else ""}"></span>{mode}<span>1 estação · FIFO com justiça por cota</span></div>',
        unsafe_allow_html=True,
    )
    with st.container(key="metrics"):
        cols = st.columns(4)
        cols[0].metric(
            "RELÓGIO SIMULADO",
            f"{engine.current_time // 60:02}:{engine.current_time % 60:02}",
        )
        cols[1].metric("NA FILA", len(engine.queue.snapshot()))
        cols[2].metric("FINALIZADOS", m["completed"])
        cols[3].metric(
            "INÍCIOS NO SLA",
            "—" if m["compliance"] is None else f"{m['compliance']:.1f}%",
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
    with st.container(border=True, key="station"):
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
                else "Pedidos prontos para começar. Clique em Iniciar simulação ou avance +1 segundo."
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
                st.markdown(
                    '<div class="empty-lane">Fila livre<span>Novos pedidos aparecerão aqui.</span></div>',
                    unsafe_allow_html=True,
                )
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
    """Mantém navegação/formulários estáveis; só a operação usa temporizador."""
    st.set_page_config(
        page_title="KitchenFlow · Cozinha em movimento", page_icon="🍔", layout="wide"
    )
    init_session()
    engine = st.session_state.engine
    st.markdown(
        "<style>"
        + (ROOT / "assets/style.css").read_text(encoding="utf-8")
        + "</style>",
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown(
            '<div class="brand"><span class="brand-mark">KF</span><div>KitchenFlow<small>COZINHA EM MOVIMENTO</small></div></div>',
            unsafe_allow_html=True,
        )
        with st.form("new_order"):
            st.subheader("Novo pedido")
            st.text_input(
                "Identificador (opcional)",
                max_chars=64,
                key="order_id",
                placeholder="Ex.: MESA-12",
            )
            st.selectbox("Canal", list(CHANNELS), key="channel")
            st.selectbox("Complexidade", list(COMPLEXITIES), key="complexity")
            st.checkbox("Entregador já aguarda", key="courier")
            st.form_submit_button(
                "Adicionar à fila",
                type="primary",
                width="stretch",
                on_click=submit_order,
            )
        st.caption(
            "Adicionar coloca na fila. O controle Iniciar simulação faz o relógio andar."
        )
        with st.expander("Cenários prontos", expanded=True):
            scenario = st.selectbox(
                "Perfil", ["Justiça 3:1", "Aleatório"], key="scenario"
            )
            count = st.number_input("Pedidos no lote", 1, 200, 7, key="count")
            seed = st.number_input("Semente reproduzível", 0, 999999, 42, key="seed")
            percent = st.slider("Deliveries urgentes (%)", 0, 100, 60, key="percent")
            if st.button("Adicionar cenário", key="burst", width="stretch"):
                act(
                    lambda: add_burst(engine, count, seed, percent, scenario),
                    "Cenário adicionado. Inicie a simulação ou use os passos manuais.",
                )
            st.caption(
                "Justiça: 1 padrão e demais deliveries com entregador. A urgência depende da regra ativa; o percentual vale no perfil aleatório."
            )
        with st.expander("Chegadas automáticas"):
            st.checkbox(
                "Chegadas durante reprodução", key="arrivals", on_change=reset_clock
            )
            st.number_input(
                "Intervalo entre chegadas (s simulados)",
                1,
                3600,
                30,
                key="arrival_interval",
                on_change=reset_clock,
            )
            st.caption(
                "Usa a semente e o percentual do cenário. Só gera pedidos com a reprodução ligada."
            )
        with st.expander("Nova sessão"):
            st.caption(
                "Exporte o histórico antes de começar outra simulação. No Streamlit Cloud, o disco é temporário e pode ser perdido em reinícios."
            )
            confirm = st.checkbox("Confirmo iniciar outra sessão", key="reset_confirm")
            st.button(
                "Iniciar nova sessão",
                disabled=not confirm,
                key="reset",
                on_click=reset_session,
            )
        st.markdown(
            '<div class="sidebar-footer">PROJETO A3 · SIMULAÇÃO ACADÊMICA<br>Python / Streamlit / SQLite</div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div class="hero"><div class="eyebrow">KITCHENFLOW / CENTRAL DE OPERAÇÕES</div><h1>Uma cozinha. Cada segundo conta.</h1><p>Organize a fila, acompanhe o preparo e experimente novas decisões.</p><span class="hero-tag">Laboratório de fast food</span></div>',
        unsafe_allow_html=True,
    )
    # Os controles ficam fora do fragmento: não piscam nem perdem foco a cada segundo.
    with st.container(key="playback_controls"):
        start, speed, one, minute = st.columns(
            [2.1, 1.5, 1, 1.2], vertical_alignment="bottom"
        )
        start.button(
            "Pausar simulação" if st.session_state.auto else "Iniciar simulação",
            key="play",
            type="primary",
            width="stretch",
            on_click=toggle_playback,
            icon=":material/pause:"
            if st.session_state.auto
            else ":material/play_arrow:",
        )
        speed.selectbox(
            "Velocidade",
            [1, 5, 15, 30, 60],
            index=1,
            format_func=lambda v: f"{v}× · {v} s/s",
            key="speed",
            on_change=reset_clock,
        )
        if one.button(
            "+1 segundo", key="step1", disabled=st.session_state.auto, width="stretch"
        ):
            act(lambda: manual_advance(engine, 1), "Relógio avançado em 1 segundo.")
        if minute.button(
            "+60 segundos",
            key="step60",
            disabled=st.session_state.auto,
            width="stretch",
        ):
            act(lambda: manual_advance(engine, 60), "Relógio avançado em 60 segundos.")
        with st.expander("Avanço personalizado"):
            seconds = st.number_input(
                "Avanço manual (s)", 1, 86400, 180, key="manual_seconds"
            )
            if st.button("Avançar", key="advance", disabled=st.session_state.auto):
                act(lambda: manual_advance(engine, seconds), "Relógio avançado.")
        st.caption(
            "Iniciar move o relógio. Pausar permite avançar passo a passo. Pausar a cozinha, no Laboratório, suspende somente a produção."
        )

    notice = st.session_state.pop("notice", None)
    if notice:
        getattr(st, notice[0])(notice[1])
    # A navegação também é estável. Abrir Histórico atualiza o relatório sob demanda.
    operation, lab, audit, guide = st.tabs(
        ["Operação ao vivo", "Laboratório", "Logs e auditoria", "Como demonstrar"],
        key="workspace",
    )

    @st.fragment(run_every=1 if st.session_state.auto else None, key="kitchen_live")
    def live():
        """Consome tempo acumulado sem resetá-lo por um clique ou rerun antecipado."""
        if st.session_state.auto:
            try:
                due = st.session_state.playback_clock.consume(
                    time.monotonic(), st.session_state.speed
                )
                if due:
                    advance_playback(
                        engine,
                        due,
                        arrivals=st.session_state.arrivals,
                        interval=st.session_state.arrival_interval,
                        seed=st.session_state.seed,
                        urgent_percent=st.session_state.percent,
                    )
            except (ValueError, TypeError, sqlite3.Error) as error:
                st.session_state.auto = False
                st.session_state.notice = ("error", f"Reprodução interrompida: {error}")
                st.rerun()
        dashboard(engine)

    with operation:
        live()
    with lab:
        laboratory(engine)
    with audit:
        history(engine)
    with guide:
        st.subheader("Da fila à decisão, em poucos passos")
        st.markdown("""1. Em uma sessão nova, carregue **Justiça 3:1** com sete pedidos.
2. Para observar continuamente, clique em **Iniciar simulação**. O relógio e a produção avançam na velocidade selecionada.
3. Para demonstrar a cota com precisão, pause a simulação, avance **1 segundo** e depois **60 segundos** três vezes: o padrão começa no segundo 181 se você partiu de zero.
4. No **Laboratório**, altere tempos e metas. SLA e urgência novos afetam próximas chegadas; preparo afeta próximos inícios.
5. Pause a cozinha, avance o relógio e observe a espera crescer. Retome ou redefina o restante do preparo.
6. Abra **Histórico**, confira os registros e baixe o SQL completo.

**SLA = início do preparo − entrada na fila.** A cota protege oportunidades; não aumenta a capacidade da cozinha. Sobrecarga pode exceder metas.

Uma estação, sem trocar o pedido ativo por outro. Os valores são hipóteses didáticas configuráveis. A reprodução depende da aba aberta; ao voltar de uma longa suspensão, recupera no máximo cinco segundos reais por atualização.""")


if __name__ == "__main__":
    main()
