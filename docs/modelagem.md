# Modelagem orientada a objetos

**Etapa 1:** contrato e modelo inicial. As classes futuras aparecem no diagrama para orientar as sete etapas; somente `OrderChannel`, `OrderComplexity`, `TicketStatus`, `PriorityLevel`, `SlaStatus`, `QueueEventType`, `QueueEvent` e `BusinessRules` são implementadas nesta etapa.

## Diagrama inicial de classes

```mermaid
classDiagram
    class OrderChannel {
        <<enumeration>>
        DELIVERY
        PICKUP
        COUNTER
    }
    class OrderComplexity {
        <<enumeration>>
        SIMPLE
        MEDIUM
        COMPLEX
    }
    class TicketStatus {
        <<enumeration>>
        WAITING
        PREPARING
        COMPLETED
        CANCELLED
    }
    class PriorityLevel {
        <<enumeration>>
        URGENT
        STANDARD
    }
    class SlaStatus {
        <<enumeration>>
        WAITING
        AT_RISK
        MET
        BREACHED
    }
    class QueueEventType {
        <<enumeration>>
        ENQUEUED
        SERVICE_STARTED
        PREPARATION_COMPLETED
        CANCELLED
    }
    class Order {
        +str id
        +OrderChannel channel
        +OrderComplexity complexity
        +bool courier_waiting
    }
    class Ticket {
        +str id
        +Order order
        +PriorityLevel priority
        +int arrival_sequence
        +TicketStatus status
        +int enqueued_at
        +int? service_started_at
        +int? completed_at
        +wait_seconds(now) int
        +start(now) None
        +complete(now) None
        +cancel() None
    }
    class BusinessRules {
        +Mapping sla_targets_seconds
        +Mapping preparation_times_seconds
        +int urgent_quota
        +float at_risk_fraction
        +priority_for(channel, courier_waiting) PriorityLevel
        +sla_seconds_for(channel) int
        +preparation_seconds_for(complexity) int
    }
    class PriorityQueue {
        -deque urgent
        -deque standard
        +enqueue(ticket) None
        +has_waiting(priority) bool
        +pop_oldest(priority) Ticket
        +snapshot() TicketList
    }
    class PriorityPolicy {
        <<abstract>>
        +choose_priority(queue) PriorityLevel or None
        +record_started(priority) None
    }
    class QuotaFairnessPolicy {
        -int consecutive_urgent_starts
        +choose_priority(queue) PriorityLevel or None
        +record_started(priority) None
    }
    class SlaMonitor {
        +wait_seconds(ticket, now) int
        +status(ticket, now) SlaStatus
    }
    class Dispatcher {
        +start_next(now) Ticket or None
    }
    class SimulationEngine {
        +int current_second
        +enqueue(order) Ticket
        +advance(seconds) SimulationSnapshot
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
        +int or None wait_seconds
        +int or None sla_target_seconds
        +SlaStatus or None sla_status
    }
    class AuditLogger {
        +record(event) None
        +export_sql() str
    }

    Ticket *-- Order : contem
    QuotaFairnessPolicy --|> PriorityPolicy : implementa
    PriorityQueue ..> Ticket : armazena
    Dispatcher --> PriorityQueue : consulta e retira
    Dispatcher --> PriorityPolicy : escolhe faixa
    Dispatcher --> SlaMonitor : mede espera
    SimulationEngine --> Dispatcher : coordena atendimento
    SimulationEngine --> AuditLogger : registra eventos
    AuditLogger ..> QueueEvent : persiste
    Order --> OrderChannel
    Order --> OrderComplexity
    Ticket --> TicketStatus
    Ticket --> PriorityLevel
    SlaMonitor --> SlaStatus
    BusinessRules ..> Order : classifica dados
    BusinessRules ..> PriorityLevel
    BusinessRules ..> SlaStatus
```

## Responsabilidades e limites

- **Domínio:** `Order`, `Ticket` e enums representam dados e estados válidos. `Ticket` mantém um `Order` por composição e registra a prioridade definida na entrada.
- **Regras:** `BusinessRules` fornece prioridades, metas de SLA, duração de preparo, cota e limiar de risco. Ela não enfileira nem despacha tickets.
- **Estrutura:** `PriorityQueue` mantém FIFO separada por nível. Ela não decide qual nível deve vencer.
- **Política:** `PriorityPolicy` define o contrato; `QuotaFairnessPolicy` aplica a cota sem retirar tickets da estrutura.
- **Serviços:** `SlaMonitor` calcula espera e estado do SLA; `Dispatcher` escolhe e inicia o próximo ticket; `SimulationEngine` controla tempo e preparo.
- **Auditoria:** serviços emitem `QueueEvent`. `AuditLogger` recebe eventos e, em outra etapa, os grava e exporta SQL.
- **Interface:** Streamlit chama o motor e apresenta dados; não acessa ou altera diretamente as filas internas.

## Contratos compartilhados

| Classe | Método ou atributo | Contrato |
|---|---|---|
| `BusinessRules` | `priority_for(channel, courier_waiting)` | Recebe canal como texto ou enum e `courier_waiting` como `bool`; retorna `URGENT` apenas para delivery com entregador aguardando. |
| `BusinessRules` | `sla_seconds_for(channel)` | Recebe canal como texto ou enum e retorna a meta configurada em segundos. |
| `BusinessRules` | `preparation_seconds_for(complexity)` | Recebe complexidade como texto ou enum e retorna a duração configurada. |
| `BusinessRules` | `urgent_quota` | Retorna a quantidade máxima configurada de inícios urgentes consecutivos quando há padrão esperando. |
| `PriorityQueue` | `enqueue(ticket)` | Coloca no final da faixa correspondente, preservando FIFO. |
| `PriorityQueue` | `has_waiting(priority)` | Informa se há ticket aguardando na faixa. |
| `PriorityQueue` | `pop_oldest(priority)` | Remove e retorna o primeiro ticket da faixa; faixa vazia gera erro de fila vazia. |
| `PriorityQueue` | `snapshot()` | Devolve um retrato em ordem de atendimento, sem alterar filas. |
| `PriorityPolicy` | `choose_priority(queue)` | Retorna a faixa escolhida ou `None` se ambas estiverem vazias; não retira o ticket. |
| `PriorityPolicy` | `record_started(priority)` | Atualiza a política somente quando o despacho realmente inicia. |
| `SlaMonitor` | `wait_seconds(ticket, now)` | Calcula `now - enqueued_at`, sem incluir o tempo de preparo. |
| `SlaMonitor` | `status(ticket, now)` | Classifica espera, risco, cumprimento ou excesso conforme o estado e o limite. |
| `Dispatcher` | `start_next(now)` | Escolhe e inicia um ticket, ou retorna `None` se não houver fila. |
| `SimulationEngine` | `enqueue(order)` | Cria ticket no segundo simulado atual e emite evento de entrada. |
| `SimulationEngine` | `advance(seconds)` | Avança o relógio e conclui preparo quando seu tempo termina. |
| `AuditLogger` | `record(event)` | Recebe um evento de fila tipado, sem depender de Streamlit. |
| `AuditLogger` | `export_sql()` | Retorna SQL executável para reconstruir eventos gravados. |

## Complexidade prevista para as filas

Com uma `collections.deque` por prioridade, inserir e remover no início/final custam **O(1)**. Consultar a disponibilidade de uma faixa custa **O(1)**. Criar um `snapshot()` completo visita os tickets e custa **O(n)**. A política consulta somente as duas faixas, então escolher a próxima faixa custa **O(1)**.
