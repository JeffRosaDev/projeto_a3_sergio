# Dicionário de dados, classes e métodos

Este documento descreve o vocabulário acordado na Etapa 1. Os elementos marcados como **planejados** ainda serão implementados nas etapas seguintes; os demais identificam o contrato inicial.

## Enumerações implementadas

| Nome | Valores | Significado |
|---|---|---|
| `OrderChannel` | `DELIVERY`, `PICKUP`, `COUNTER` | Canal pelo qual o pedido chega. |
| `OrderComplexity` | `SIMPLE`, `MEDIUM`, `COMPLEX` | Classe de duração estimada do preparo simulado. |
| `TicketStatus` | `WAITING`, `PREPARING`, `COMPLETED`, `CANCELLED` | Estado operacional do ticket. |
| `PriorityLevel` | `URGENT`, `STANDARD` | Faixa definida ao entrar na fila. |
| `SlaStatus` | `WAITING`, `AT_RISK`, `MET`, `BREACHED` | Situação da espera em relação à meta de SLA. |
| `QueueEventType` | `ENQUEUED`, `SERVICE_STARTED`, `PREPARATION_COMPLETED`, `CANCELLED` | Tipo de evento de fila emitido pelo motor. |

## Classes implementadas na Etapa 1

### `BusinessRules`

Configuração imutável para calcular prioridade e consultar metas de SLA e tempos de preparo. Seus mapas são copiados e protegidos contra mutação após a construção.

| Atributo | Tipo | Padrão | Descrição |
|---|---|---:|---|
| `sla_targets_seconds` | `Mapping[OrderChannel, int]` | Delivery 180; retirada 300; balcão 480 | Meta de espera até iniciar o preparo, em segundos. |
| `preparation_times_seconds` | `Mapping[OrderComplexity, int]` | Simples 60; médio 120; complexo 180 | Duração de preparo simulado, em segundos. |
| `urgent_quota` | `int` | 3 | Máximo de inícios urgentes consecutivos quando há padrão aguardando. |
| `at_risk_fraction` | `float` | 0.8 | Fração da meta a partir da qual a espera é considerada em risco. |

| Método | Entrada | Saída | Regra |
|---|---|---|---|
| `priority_for(channel, courier_waiting)` | `OrderChannel`, `bool` | `PriorityLevel` | Urgente se o canal for delivery e o entregador já aguardar; padrão nos outros casos. |
| `sla_seconds_for(channel)` | `OrderChannel` | `int` | Consulta a meta definida para o canal. |
| `preparation_seconds_for(complexity)` | `OrderComplexity` | `int` | Consulta o tempo definido para a complexidade. |

A construção rejeita mapas incompletos, enumerações incorretas, tempos não inteiros ou não positivos, cota não positiva e limiar fora de `(0, 1]`.

### `QueueEvent`

Evento imutável e independente de SQLite/Streamlit. A fotografia da fila contém os IDs dos tickets **que continuam aguardando depois do evento**; o ticket identificado por `ticket_id` pode estar em atendimento quando `event_type` for `SERVICE_STARTED`.

| Atributo | Tipo | Nulo? | Descrição |
|---|---|---|---|
| `event_id` | `str` | Não | Identificador único criado pela camada que emite o evento. |
| `ticket_id` | `str` | Não | Identificador do ticket relacionado. |
| `event_type` | `QueueEventType` | Não | Entrada, início, conclusão ou cancelamento. |
| `simulated_second` | `int` | Não | Instante do evento no relógio da simulação. |
| `channel` | `OrderChannel` | Não | Canal do pedido. |
| `priority` | `PriorityLevel` | Não | Prioridade registrada para o ticket. |
| `queue_size_before` | `int` | Não | Quantidade de tickets aguardando imediatamente antes do evento. |
| `queue_size_after` | `int` | Não | Quantidade de tickets aguardando imediatamente depois do evento. |
| `queue_snapshot` | `tuple[str, ...]` | Não | IDs dos tickets que ainda aguardam, na ordem exibida. |
| `wait_seconds` | `int \| None` | Sim | Espera calculada quando o ticket inicia; ausente antes disso. |
| `sla_target_seconds` | `int \| None` | Sim | Meta do canal em segundos; opcional em eventos que ainda não iniciaram. |
| `sla_status` | `SlaStatus \| None` | Sim | Situação calculada, quando aplicável. |

## Classes planejadas para as etapas seguintes

| Classe | Responsabilidade prevista | Etapa |
|---|---|---:|
| `Order` | Manter ID fictício, canal, complexidade e indicação de entregador aguardando. | 2 |
| `Ticket` | Relacionar um pedido, prioridade, sequência de chegada, estado e horários. | 2 |
| `PriorityQueue` | Guardar tickets em duas faixas FIFO e fornecer consulta/remoção/snapshot. | 3 |
| `PriorityPolicy` | Definir a interface de escolha de faixa e notificação de início. | 4 |
| `QuotaFairnessPolicy` | Garantir a cota de urgentes sem retirar tickets da fila. | 4 |
| `SlaMonitor` | Calcular espera e estado de SLA. | 5 |
| `Dispatcher` | Selecionar o ticket, iniciar atendimento e atualizar política/SLA. | 5 |
| `SimulationEngine` | Controlar relógio, estação, preparo e chegadas. | 5 |
| `AuditLogger` | Persistir eventos em SQLite e exportar SQL executável. | 6 |
| Interface Streamlit | Inserir pedidos de simulação e exibir fila, serviço, espera, SLA e histórico. | 7 |

## Convenções compartilhadas

- Horários e durações são segundos inteiros no relógio simulado.
- Nomes de tipos/enums são em inglês no código; a documentação e a interface são em português.
- Métodos públicos são documentados e não acessam a interface visual.
- `None` indica ausência de uma decisão/horário; erro de tipo ou valor inválido deve gerar exceção clara.
- Identificadores servem à simulação; dados pessoais e pagamentos não são coletados.
