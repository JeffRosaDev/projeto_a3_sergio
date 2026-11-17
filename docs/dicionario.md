# Dicionário final de dados e métodos

O [diagrama completo](../entregas/final/diagrama_completo.md) contém o catálogo detalhado de atributos, tipos, visibilidade e métodos, e o esquema relacional com todos os campos.

- `Order`: dados imutáveis do pedido; ID fictício de até 64 caracteres, canal, complexidade, chegada inteira não negativa, entregador aguardando.
- `Ticket`: contém pedido, sequência, regras de admissão, prioridade, estado e horários. Início/conclusão são opcionais antes da transição.
- `BusinessRules`: mapas imutáveis de metas/preparo, cota positiva, fração de risco em (0,1] e opção de priorizar novos deliveries.
- `PriorityQueue`: duas deques FIFO e conjunto de IDs; snapshot é uma nova lista de referências, agrupada por faixa.
- `PriorityPolicy`/`QuotaFairnessPolicy`: escolhe faixa sem remover e registra inícios reais; possui checkpoint/restauração para rollback.
- `SlaMonitor`: espera congelada no início; meta retirada das regras do ticket e limiar corrente para alertas.
- `Dispatcher`: seleção, transição de início, retirada e evento SQL em unidade recuperável.
- `SimulationEngine`: entrada, avanço, configuração, pausa da cozinha, redefinição de restante e cancelamento; transação engloba memória e SQL.
- `SimulationSnapshot`: relógio, ticket em preparo opcional e lista das faixas. Não é cópia histórica profunda.
- `QueueEvent`: evento congelado com ID, ticket, tipo/instante, canal, faixa, contagens, IDs aguardando e métricas opcionais.
- `AuditLogger`: conexão por sessão com RLock; savepoints, INSERT, leitura, exportação autossuficiente e fechamento.
- `simulation_actions`: registra configuração, lotes e incidentes em JSON.
- `audit_sequence`: sequência inteira comum a eventos e ações; resolve empates do relógio simulado.

Métodos privados começam com `_`; nomes públicos são contratos dos módulos. O Python usa convenções de visibilidade, não restrições de acesso equivalentes a Java. `None` representa dado ainda inexistente, não zero. Unidades temporais são sempre segundos simulados, salvo `recorded_at`, que é o timestamp real do SQLite.

## Enumerações compartilhadas

- `OrderChannel`: DELIVERY (entrega), PICKUP (retirada), COUNTER (balcão).
- `OrderComplexity`: SIMPLE, MEDIUM, COMPLEX; selecionam uma duração configurável.
- `PriorityLevel`: URGENT e STANDARD; a prioridade de um ticket não muda após admissão.
- `TicketStatus`: WAITING, PREPARING, COMPLETED, CANCELLED; controla transições operacionais.
- `SlaStatus`: WAITING (aguardando abaixo do alerta), AT_RISK, MET e BREACHED. MET só se aplica depois do início.
- `QueueEventType`: ENQUEUED, SERVICE_STARTED, PREPARATION_COMPLETED e CANCELLED.

As enums herdam `str` e `Enum`: fornecem valores legíveis no SQL e restringem o vocabulário do domínio. `@unique` impede aliases acidentais.

## Regras — domain/rules.py

`BusinessRules` é uma dataclass congelada. `sla_targets_seconds` mapeia canal para meta; `preparation_times_seconds` mapeia complexidade para duração; `prioritize_delivery` habilita urgência; `urgent_quota` limita inícios urgentes consecutivos; `at_risk_fraction` define o alerta.

- `__post_init__() -> None`: valida chaves completas dos mapas, tempos inteiros positivos, cota inteira positiva, booleano de urgência e fração numérica em (0, 1]. Copia os mapas para impedir mudanças pelo dicionário original.
- `priority_for(channel, courier_waiting) -> PriorityLevel`: recebe valores simples, normaliza canal e atribui URGENT somente a delivery com entregador presente e prioridade habilitada. Não depende de `Order`.
- `sla_seconds_for(channel) -> int`: consulta a meta do canal normalizado.
- `preparation_seconds_for(complexity) -> int`: consulta a duração da complexidade normalizada.
- `as_dict() -> dict`: cria representação serializável com nomes das enums e todos os parâmetros para registrar a configuração.
- `_channel_value(channel) -> OrderChannel` e `_complexity_value(complexity) -> OrderComplexity`: aceitam enum ou texto válido, removem espaços e normalizam caixa; rejeitam valores desconhecidos.
- `_validated_map(values, expected_keys, name)`: função interna que valida e copia os mapas; o resultado usa `MappingProxyType` para bloquear mutações diretas.

Tipos incompatíveis produzem `TypeError`; valores fora do domínio produzem `ValueError`. Criar outra configuração não modifica instâncias antigas. As consultas aos mapas têm custo esperado O(1).

## Pedido e ciclo de vida — domain/order.py e ticket.py

`Order` é imutável. Campos públicos: `id: str`, `channel: OrderChannel`, `complexity: OrderComplexity`, `arrival_time: int` e `courier_waiting: bool`.

- `Order.__post_init__()`: exige ID textual não vazio após retirar espaços, com até 64 caracteres; enums corretas; chegada inteira não negativa e booleano real. Um `bool` não é aceito como número de segundos.
- `Ticket.__post_init__()`: exige `Order`, sequência inteira positiva e `BusinessRules`; define `enqueued_at` pela chegada e calcula a prioridade uma vez.
- `Ticket.id -> str`: propriedade que delega o ID ao pedido contido; evita armazenar duas identidades independentes.
- `start_preparation(now) -> None`: WAITING → PREPARING; registra `started_at`. Rejeita outro estado, horário inválido ou início anterior à chegada.
- `complete_preparation(now) -> None`: PREPARING → COMPLETED; registra `completed_at`. Rejeita outro estado ou conclusão anterior ao início.
- `cancel() -> None`: WAITING → CANCELLED; não apaga o ticket. O instante do cancelamento fica no evento de auditoria, não em um atributo `cancelled_at`.
- `_validate_time(now) -> None`: validador compartilhado de instantes inteiros não negativos.

Além de `order`, `sequence` e `rules`, Ticket mantém `priority`, `status`, `enqueued_at`, `started_at` e `completed_at`. Os dois últimos começam em `None`. As transições isoladas custam O(1); a aplicação deve chamá-las pelo motor para incluir persistência e verificação da estação única.

## Eventos — domain/events.py

`QueueEvent` é uma dataclass congelada com slots. `event_id` identifica o registro e `ticket_id` identifica o pedido. `event_type`, `simulated_second`, `channel` e `priority` descrevem o fato. `queue_size_before` e `queue_size_after` contam apenas aguardando; `queue_snapshot: tuple[str, ...]` contém seus IDs depois do evento. `wait_seconds`, `sla_target_seconds` e `sla_status` são métricas opcionais.

- `__post_init__()`: valida IDs não vazios, enums, contagens e instante; exige que o comprimento do snapshot coincida com a contagem posterior. Não impõe sozinho todas as regras de transição; o motor produz o evento no contexto correto.
- `_validate_optional_seconds(name, value)`: rejeita segundos negativos, fracionários ou booleanos. A meta, quando presente, deve ser maior que zero.

Na entrada e no cancelamento sem início, a espera e o resultado de SLA do evento ficam `None`; no início/conclusão registram a espera até o início. A validação e a cópia dos IDs têm custo O(n) na fila.

## Estrutura de filas — queues/priority_queue.py

`_queues: dict[PriorityLevel, deque[Ticket]]` armazena uma deque por faixa. `_ids: set[str]` indexa apenas IDs aguardando. A unicidade em toda a sessão é responsabilidade de `SimulationEngine.tickets`.

- `__init__()`: cria duas deques vazias e o conjunto de IDs.
- `enqueue(ticket) -> None`: exige Ticket em WAITING e ID ausente; acrescenta ao fim da faixa. Não calcula prioridade nem registra SQL.
- `has_waiting(priority) -> bool`: consulta se a faixa possui itens; aceita enum ou texto normalizável.
- `pop_oldest(priority) -> Ticket`: remove o primeiro da faixa e seu ID do conjunto. `IndexError` se estiver vazia.
- `snapshot() -> list[Ticket]`: nova lista de referências, urgentes seguidos de padrões; não altera deques nem simula a política de cota.
- `restore(tickets) -> None`: recompõe faixas e índice a partir de checkpoint confiável. Uso interno de recuperação, não entrada livre do usuário.
- `remove(ticket) -> None`: remove um item específico e seu ID; usado pelo cancelamento do motor. Item ausente pode causar `ValueError`/`KeyError`.
- `_validate_priority(priority) -> PriorityLevel`: normaliza enum/texto e rejeita faixa inexistente.

Inserir, consultar e retirar da ponta têm custo esperado O(1); snapshot, restauração e remoção arbitrária custam O(n). Modificar diretamente um Ticket obtido no snapshot viola o contrato de uso: snapshots não são cópias profundas.

## Política de justiça — queues/priority_policy.py

`PriorityPolicy(ABC)` define cinco operações abstratas. `QuotaFairnessPolicy` implementa todas por herança e encapsula `_urgent_quota` e `_consecutive_urgent_starts`.

- `__init__(rules=None)`: usa padrões quando não há configuração; começa com contador zero.
- `choose_priority(queue) -> PriorityLevel | None`: urgente enquanto houver cota; depois padrão se existir; urgente se padrão estiver vazio; `None` quando ambas vazias. Consulta sem modificar contador/fila.
- `record_started(priority) -> None`: incrementa contador urgente até a cota, ou zera ao iniciar padrão. Exige `PriorityLevel`; é chamado somente após início efetivo.
- `consecutive_urgent_starts -> int`: leitura pública do contador, limitada à cota.
- `configure(rules) -> None`: atualiza a cota e limita o contador acumulado à nova cota; não concede contagem zero a cada mudança.
- `checkpoint() -> tuple[int, int]`: devolve cota e contador para recuperação.
- `restore(state) -> None`: restaura a dupla previamente salva. Destina-se a checkpoints internos confiáveis.

As operações são O(1). A garantia é entre oportunidades da faixa padrão, sob duração finita e cozinha em funcionamento. Pedidos padrão podem ter outros padrões mais antigos à frente.

## Espera e despacho — services/sla_monitor.py e dispatcher.py

`SlaMonitor.rules` mantém a configuração corrente do alerta. A meta contratada vem de `ticket.rules`, preservada na admissão.

- `SlaMonitor.__init__(business_rules=None)`: usa configuração recebida ou padrão.
- `wait_seconds(ticket, now) -> int`: retorna `(started_at se existir, senão now) - enqueued_at`; exige instante válido não anterior à chegada. Usa `is not None`, pois início no segundo zero é válido.
- `status(ticket, now) -> SlaStatus`: depois do início, MET se espera <= meta, senão BREACHED. Aguardando: BREACHED acima da meta; AT_RISK a partir da fração; WAITING abaixo dela. Cancelados ficam fora dos indicadores de cumprimento.
- `Dispatcher.__init__(queue, policy, sla_monitor, audit_logger)`: recebe colaboradores por injeção; não cria uma segunda fila.
- `start_next(now) -> Ticket | None`: consulta a política, inicia o primeiro da faixa, retira da fila, atualiza contador e grava SERVICE_STARTED. Com fila vazia retorna `None`. Em falha, restaura estado do ticket, ordem da fila e política, além do rollback SQL.

As consultas de SLA custam O(1). O despacho inclui snapshots O(n). `Dispatcher` sozinho não controla ocupação da cozinha: o motor chama `start_next()` somente quando a estação está livre.

## Motor — services/simulation_engine.py

Campos públicos: `dispatcher`, `queue`, `rules`, `audit_logger`; `current_time: int`; `preparing_ticket: Ticket | None`; `preparation_end_time: int`; `station_paused: bool`; `tickets: dict[str, Ticket]`. `_sequence_counter` é a sequência monotônica de admissão. `preparation_end_time` só representa um prazo ativo quando existe ticket em preparo.

- `__init__(dispatcher, queue, rules, audit_logger)`: relógio zero, estação livre, registro vazio e ação CONFIG_INITIAL.
- `enqueue(item: Order | Ticket) -> Ticket`: exige chegada no relógio atual, ID nunca usado e menos de 2000 aguardando. Ticket já construído precisa estar em WAITING, usar regras atuais e ter sequência maior que a anterior. Admite e registra ENQUEUED atomicamente.
- `advance(seconds) -> SimulationSnapshot`: inteiro entre 0 e 86400. Zero só consulta. Valor positivo processa inícios e conclusões até o destino; primeiro início no segundo seguinte. Conclusão precede novo início no mesmo segundo. Com estação pausada, desloca o prazo ativo e avança a espera sem produzir.
- `configure(rules) -> None`: exige BusinessRules e registra CONFIG_CHANGED. Atualiza motor, monitor e política. Não reclassifica tickets nem reescreve metas históricas.
- `pause_station(paused: bool) -> None`: registra STATION_PAUSE/STATION_RESUME e altera disponibilidade física. Não é o botão de reprodução do Streamlit.
- `adjust_remaining(seconds) -> None`: exige preparo ativo e inteiro entre 1 e 86400. Registra tempos antes/depois e define prazo como relógio atual + valor informado.
- `cancel(ticket_id) -> None`: exige ticket existente em espera; muda estado, retira da faixa e grava CANCELLED. O ID permanece reservado.
- `_atomic()`: context manager privado que combina savepoint SQL e checkpoint de relógio, tickets, fila, regras e política. Restaura memória em qualquer exceção, mantendo identidade dos tickets antigos.
- `_event(ticket, kind, before)`: monta QueueEvent usando estado posterior e monitor de SLA; delega INSERT ao logger.

`SimulationSnapshot` é dataclass congelada contendo `current_time`, `preparing_ticket` e `queue_snapshot`. A lista e os tickets referenciados continuam mutáveis; não é um arquivo histórico. O motor salta entre eventos relevantes em intervalos vazios, mas checkpoints/snapshots e persistência têm custo proporcional ao estado; não se promete O(1) por avanço completo.

## Auditoria — audit/audit_logger.py

`_connection` é a conexão SQLite; `_lock: RLock` serializa acesso entre threads da sessão. `DEFAULT_SCHEMA` contém as três tabelas e triggers. Identificadores gerados para savepoints e SQL estrutural vêm do código; dados de pedidos usam parâmetros SQL.

- `__init__(db_path=':memory:', schema_path=None)`: abre banco e executa schema padrão ou arquivo indicado. Caminho em disco preserva histórico. Falhas de arquivo/banco propagam exceção.
- `transaction()`: context manager de savepoint aninhável; RELEASE confirma unidade bem-sucedida, ROLLBACK TO + RELEASE desfaz falha.
- `record(event: QueueEvent) -> None`: exige evento validado; insere métricas e serializa snapshot como JSON. ID duplicado gera erro de integridade.
- `record_action(now, action, details) -> None`: gera action_id, serializa detalhes JSON e insere intervenção. É API interna de integração; entradas vêm do motor validado.
- `fetch_all() -> list[dict]`: lê eventos na ordem de inserção e decodifica `queue_snapshot` em lista.
- `actions() -> list[dict]`: lê configurações/intervenções na ordem de inserção; `details` permanece texto JSON.
- `count() -> int`: conta somente eventos operacionais, sem incluir ações.
- `export_sql(output_path=None) -> str`: percorre ordem global, inclui schema, transação e INSERTs com timestamps originais. Se caminho for dado, cria diretórios e grava UTF-8. Destino de importação deve estar vazio.
- `_sql_quote(value) -> str`: transforma NULL/número/texto em literal para exportação, duplicando aspas simples. Não substitui parâmetros na gravação normal.
- `close() -> None`: fecha a conexão; chamadas posteriores que dependam dela falham.
- `__enter__() -> AuditLogger` e `__exit__(*args)`: permitem `with AuditLogger(...)` e fechamento garantido.

`queue_events` contém os campos do QueueEvent mais `recorded_at` UTC do SQLite. `simulation_actions` contém `action_id`, `simulated_second`, `action`, `details`, `recorded_at`. `audit_sequence` contém `sequence`, `entry_id`, `entry_kind`: a ordem total entre as duas tabelas é criada por triggers. Veja todos os tipos SQL no [diagrama](../entregas/final/diagrama_completo.md) e em [schema.sql](../sql/schema.sql). UPDATE/DELETE comuns são bloqueados; um administrador capaz de remover triggers não é impedido.

## Cenários, indicadores e interface

- `create_engine(rules=None, db_path=':memory:') -> SimulationEngine`: fábrica que conecta fila, política, monitor, logger e motor. Não importa Streamlit; serve a testes e scripts.
- `add_burst(engine, count=7, seed=42, urgent_percent=60, scenario='Aleatório')`: lote atômico de 1 a 200 pedidos, usando Random local. Justiça 3:1 cria primeiro um padrão e depois deliveries com entregador; configuração corrente ainda determina a prioridade efetiva. Aleatório usa percentual e complexidades sorteadas. Gera IDs disponíveis e ação BURST.
- `metrics(engine) -> dict`: retorna started, completed, compliance, mean_wait e max_wait. Percentual usa apenas SERVICE_STARTED; cancelados/aguardando não integram denominador. Sem inícios, compliance é `None`, médias/máximo são zero.
- `scripts/simulate.py: run()`: executa três condições comparáveis, fecha os loggers e escreve JSON/SQL em exports.
- `app.py: act(callback, message)`: executa comando e apresenta falhas esperadas sem traceback ao usuário.
- `init_session()`: cria banco exclusivo em data e guarda motor/controles no session_state.
- `ticket_card(ticket, engine)`: renderiza espera, meta e risco com texto escapado, cor e barra visual.
- `laboratory(engine)`: formulário de regras e controles de pausa, restante e cancelamento; chama serviços.
- `history(engine)`: mostra uma trilha única com resumo por registro, filtros por tipo/operação/texto e detalhes selecionáveis de pedido, fila, SLA ou ação. Exporta SQL completo e JSON filtrado sem acessar conexão privada.
- `dashboard(engine)`: relógio, indicadores, estação, faixas, previsão de próxima faixa e detalhes dos tickets.
- `main()`: configura página, widgets, sessão e fragmento. Funções locais `enqueue()`/`reset_session()` admitem pedido e iniciam sessão nova; `live()` avança automaticamente e intercala chegadas.

`CHANNELS`, `COMPLEXITIES` e `SLA_LABELS` traduzem enums para rótulos. `ROOT` resolve recursos a partir de app.py. `session_state.auto` controla a reprodução e `notice` preserva mensagens entre reruns. O fragmento automático contém apenas o painel; formulários e navegação ficam fora dele.

`PlaybackClock` (`services/playback.py`) guarda `anchor`, o último segundo real consumido. `reset(now)` inicia uma janela após pausa/mudança; `consume(now, speed)` acumula frações mesmo entre cliques, retorna segundos simulados e limita recuperação a cinco segundos reais por ciclo. `advance_playback()` intercala chegadas nas fronteiras configuradas, em transação única. Não é relógio de precisão comercial.

`AuditLogger.timeline()` une eventos e ações pela sequência global. A aba Logs e auditoria filtra operação/ID/detalhes, mostra até 500 resultados e exporta todos os filtrados em JSON. SQL inclui o banco completo. `toggle_playback()` registra PLAYBACK_STARTED/PLAYBACK_PAUSED; `manual_advance()` registra TIME_ADVANCED com instante anterior/posterior. A trilha descreve operações bem-sucedidas da sessão, sem autenticação/autoria pessoal.
