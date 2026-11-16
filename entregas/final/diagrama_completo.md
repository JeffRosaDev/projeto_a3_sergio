# KitchenFlow — diagrama completo do projeto

Versão final de 15/11/2026. `+` indica API pública; `-` indica detalhe interno por convenção Python. A implementação é a referência para assinaturas. Diagramas separados tornam os relacionamentos legíveis; o catálogo abaixo complementa atributos e métodos.

## 1. Arquitetura e fronteiras

```mermaid
flowchart TD
  User[Operador ou apresentador] --> UI[app.py / Streamlit]
  UI --> Session[session_state / motor por sessão]
  UI --> Controls[Pedidos / laboratório / cenários / relógio]
  Controls --> Engine[SimulationEngine]
  Engine --> Domain[Order + Ticket + BusinessRules]
  Engine --> Dispatcher[Dispatcher]
  Dispatcher --> Queue[PriorityQueue / duas deques FIFO]
  Dispatcher --> Policy[QuotaFairnessPolicy]
  Dispatcher --> SLA[SlaMonitor]
  Engine --> Audit[AuditLogger]
  Dispatcher --> Audit
  Audit --> DB[(SQLite exclusivo em data/)]
  DB --> Events[queue_events]
  DB --> Actions[simulation_actions]
  DB --> Sequence[audit_sequence]
  Engine --> Snapshot[SimulationSnapshot]
  Snapshot --> UI
  Audit --> Export[SQL executável / schema e dados]
  Export --> Rebuild[(Banco vazio / histórico reconstruído)]
  Scenarios[scenarios.py / Random com semente] --> Engine
  Tests[unittest + AppTest + testes de navegador] -. valida .-> Engine
  Tests -. valida .-> UI
```

## 2. Classes, composição, herança e dependências

```mermaid
classDiagram
  class BusinessRules {
    +Mapping sla_targets_seconds
    +Mapping preparation_times_seconds
    +bool prioritize_delivery
    +int urgent_quota
    +float at_risk_fraction
    +priority_for(channel, courier_waiting) PriorityLevel
    +sla_seconds_for(channel) int
    +preparation_seconds_for(complexity) int
    +as_dict() dict
    -_channel_value(channel) OrderChannel
    -_complexity_value(complexity) OrderComplexity
  }
  class Order {
    +str id
    +OrderChannel channel
    +OrderComplexity complexity
    +int arrival_time
    +bool courier_waiting
    +__post_init__()
  }
  class Ticket {
    +Order order
    +int sequence
    +BusinessRules rules
    +PriorityLevel priority
    +TicketStatus status
    +int enqueued_at
    +int started_at
    +int completed_at
    +id() str
    +start_preparation(now)
    +complete_preparation(now)
    +cancel()
    -_validate_time(now)
  }
  class PriorityQueue {
    -dict _queues
    -set _ids
    +enqueue(ticket)
    +has_waiting(priority) bool
    +pop_oldest(priority) Ticket
    +snapshot() list
    +remove(ticket)
    +restore(tickets)
    -_validate_priority(priority)
  }
  class PriorityPolicy {
    <<abstract>>
    +choose_priority(queue) PriorityLevel
    +record_started(priority)
    +configure(rules)
    +checkpoint() tuple
    +restore(state)
  }
  class QuotaFairnessPolicy {
    -int _urgent_quota
    -int _consecutive_urgent_starts
    +consecutive_urgent_starts() int
    +choose_priority(queue) PriorityLevel
    +record_started(priority)
    +configure(rules)
    +checkpoint() tuple
    +restore(state)
  }
  class SlaMonitor {
    +BusinessRules rules
    +wait_seconds(ticket, now) int
    +status(ticket, now) SlaStatus
  }
  class PlaybackClock {
    +float anchor
    +reset(now)
    +consume(now, speed) int
  }
  class Dispatcher {
    +PriorityQueue queue
    +QuotaFairnessPolicy policy
    +SlaMonitor sla_monitor
    +AuditLogger audit_logger
    +start_next(now) Ticket
  }
  class SimulationEngine {
    +Dispatcher dispatcher
    +PriorityQueue queue
    +BusinessRules rules
    +AuditLogger audit_logger
    +int current_time
    +Ticket preparing_ticket
    +int preparation_end_time
    +bool station_paused
    +dict tickets
    -int _sequence_counter
    +enqueue(item) Ticket
    +advance(seconds) SimulationSnapshot
    +configure(rules)
    +pause_station(paused)
    +adjust_remaining(seconds)
    +cancel(ticket_id)
    -_atomic()
    -_event(ticket, kind, before)
  }
  class SimulationSnapshot {
    +int current_time
    +Ticket preparing_ticket
    +list queue_snapshot
  }
  class QueueEvent {
    +str event_id
    +str ticket_id
    +QueueEventType event_type
    +int simulated_second
    +OrderChannel channel
    +PriorityLevel priority
    +int queue_size_before
    +int queue_size_after
    +tuple queue_snapshot
    +int wait_seconds
    +int sla_target_seconds
    +SlaStatus sla_status
    +__post_init__()
    -_validate_optional_seconds(name, value)
  }
  class AuditLogger {
    -Connection _connection
    -RLock _lock
    +transaction()
    +record(event)
    +record_action(now, action, details)
    +fetch_all() list
    +actions() list
    +timeline() list
    +count() int
    +export_sql(output_path) str
    +close()
    +__enter__()
    +__exit__()
    -_sql_quote(value)
  }
  Ticket *-- Order : contém
  Ticket --> BusinessRules : contrato da entrada
  PriorityQueue o-- Ticket : referencia aguardando
  QuotaFairnessPolicy --|> PriorityPolicy
  QuotaFairnessPolicy --> BusinessRules : cota
  Dispatcher --> PriorityQueue
  Dispatcher --> QuotaFairnessPolicy
  Dispatcher --> SlaMonitor
  Dispatcher --> AuditLogger
  SimulationEngine --> Dispatcher
  SimulationEngine --> BusinessRules
  PlaybackClock ..> SimulationEngine : segundos a avancar pela interface
  SimulationEngine --> AuditLogger
  SimulationEngine --> SimulationSnapshot : produz
  SimulationEngine o-- Ticket : registro da sessão
  SlaMonitor --> Ticket
  AuditLogger ..> QueueEvent : persiste
```

`Order`, `BusinessRules` e `QueueEvent` são dataclasses congeladas. `Ticket` é mutável por transições. `SimulationSnapshot` congela a estrutura externa, mas contém referências aos tickets; não é uma cópia histórica profunda. O snapshot persistido no evento guarda apenas IDs imutáveis. Horários de início/conclusão, ticket em preparo e dados de SLA podem ser `None` antes de existirem.

## 3. Estados operacionais e SLA

```mermaid
stateDiagram-v2
  [*] --> WAITING: entrada validada
  WAITING --> PREPARING: start_preparation / estação livre
  PREPARING --> COMPLETED: prazo de preparo alcançado
  WAITING --> CANCELLED: cancelamento auditado
  COMPLETED --> [*]
  CANCELLED --> [*]
```

O estado operacional é independente de `SlaStatus`. Aguardando: WAITING → AT_RISK ao consumir o limiar; BREACHED se espera > meta. Ao iniciar: MET se espera <= meta, BREACHED caso contrário. Alterar limiar pode modificar o alerta de aguardando; a espera dos iniciados fica congelada. Cancelados não entram nos indicadores de inícios.

Enums: `OrderChannel` = DELIVERY/PICKUP/COUNTER; `OrderComplexity` = SIMPLE/MEDIUM/COMPLEX; `PriorityLevel` = URGENT/STANDARD; `TicketStatus` = WAITING/PREPARING/COMPLETED/CANCELLED; `QueueEventType` = ENQUEUED/SERVICE_STARTED/PREPARATION_COMPLETED/CANCELLED; `SlaStatus` = WAITING/AT_RISK/MET/BREACHED.

## 4. Uma decisão de atendimento e a recuperação de falhas

```mermaid
sequenceDiagram
  actor Operador
  participant UI as Streamlit
  participant E as SimulationEngine
  participant D as Dispatcher
  participant P as QuotaFairnessPolicy
  participant Q as PriorityQueue
  participant A as AuditLogger
  participant SQL as SQLite
  Operador->>UI: Avançar relógio
  UI->>E: advance(seconds)
  E->>E: checkpoint memória
  E->>A: transaction()
  A->>SQL: SAVEPOINT externo
  E->>E: avança até próximo evento
  opt prazo de preparo alcançado
    E->>E: complete_preparation(now)
    E->>A: record(PREPARATION_COMPLETED)
  end
  E->>D: start_next(now)
  D->>P: choose_priority(queue)
  P-->>D: faixa elegível
  D->>D: valida e inicia Ticket
  D->>Q: pop_oldest(priority)
  D->>P: record_started(priority)
  D->>A: record(SERVICE_STARTED)
  A->>SQL: INSERT parametrizado + sequência
  alt sucesso
    A->>SQL: RELEASE
    E-->>UI: SimulationSnapshot
  else falha de gravação
    A->>SQL: ROLLBACK TO savepoint
    E->>E: restaura relógio, fila, tickets e política
    E-->>UI: erro legível
  end
```

## 5. Modelo relacional e ordem global

```mermaid
erDiagram
  QUEUE_EVENTS {
    TEXT event_id PK
    TEXT ticket_id
    TEXT event_type
    INTEGER simulated_second
    TEXT channel
    TEXT priority
    INTEGER queue_size_before
    INTEGER queue_size_after
    TEXT queue_snapshot
    INTEGER wait_seconds
    INTEGER sla_target_seconds
    TEXT sla_status
    TEXT recorded_at
  }
  SIMULATION_ACTIONS {
    TEXT action_id PK
    INTEGER simulated_second
    TEXT action
    TEXT details
    TEXT recorded_at
  }
  AUDIT_SEQUENCE {
    INTEGER sequence PK
    TEXT entry_id UK
    TEXT entry_kind
  }
  QUEUE_EVENTS ||--|| AUDIT_SEQUENCE : evento
  SIMULATION_ACTIONS ||--|| AUDIT_SEQUENCE : acao
```

As relações com `audit_sequence` são lógicas, mantidas por triggers, não FKs: cada linha aponta para **um evento ou uma ação**, conforme `entry_kind`. `queue_snapshot` e `details` armazenam JSON. `recorded_at` é o horário real do registro; `simulated_second` é o relógio didático. Exportação percorre a sequência, inclui timestamps originais e recria a ordem ao inserir em banco vazio. Triggers bloqueiam UPDATE/DELETE; não protegem contra administrador que remova o schema.

Ações: CONFIG_INITIAL, CONFIG_CHANGED, BURST, STATION_PAUSE, STATION_RESUME e PREPARATION_ADJUSTED. Eventos: entrada, início, conclusão e cancelamento. Uma alteração de configuração não reescreve o histórico nem o contrato dos tickets antigos.

## 6. Contratos de interface, algoritmos e fronteiras

`create_engine()` injeta dependências; `add_burst()` usa Random local e transação de lote; `metrics()` agrega somente eventos de início. `app.py` usa formulários para aplicar mudanças explicitamente, `st.session_state` para manter a sessão e `st.fragment(run_every=1)` para a atualização visual. A reprodução simula segundos em passos definidos; chegadas são intercaladas segundo a segundo. O motor em si salta até eventos para evitar loops em intervalos vazios.

A fila usa duas `deque`: inserir/remover o primeiro e consultar faixa custam O(1), inclusive detecção de ID repetido pelo conjunto `_ids`. Cancelar ticket arbitrário é O(n). Snapshot, checkpoint e métricas são O(n) no número de tickets ou eventos lidos. O despacho completo inclui snapshot/auditoria e não deve ser anunciado como inteiramente O(1).

O limite de 2000 aguardando e lotes de até 200 protege a demonstração contra cliques excessivos. Não representa dimensionamento comercial. Histórico, registro de todos os tickets e eventos acumulam por sessão. A camada de UI não tem transação própria: chama o motor e mostra falhas esperadas. A auditoria usa RLock porque reruns podem usar threads distintas, enquanto cada motor pertence a uma única sessão.

## 7. Rastreabilidade das sete etapas

1. Regras, enums, contratos e base: `domain/rules.py`, `enums.py`, `events.py`.
2. Pedido e ticket: `domain/order.py`, `ticket.py`.
3. Filas: `queues/priority_queue.py`.
4. Política: `queues/priority_policy.py` (abstração e herança).
5. Serviços: `services/sla_monitor.py`, `dispatcher.py`, `simulation_engine.py`.
6. Auditoria: `audit/audit_logger.py`, `sql/schema.sql`.
7. Experiência e integração: `app.py`, `assets/style.css`, `services/scenarios.py`, testes ponta a ponta e documentos finais.

As melhorias finais ampliam os contratos das etapas anteriores sem reescrever o histórico de contribuições. Ver [README](../../README.md) para instalação, efeitos de cada controle e limites de persistência.
