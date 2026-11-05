# Planejamento técnico — Sistema de filas de prioridade para fast food

## 1. Objetivo e limites

O sistema simulará o atendimento de pedidos de uma cozinha de fast food durante um horário de pico. Uma estação prepara um pedido por vez. O programa registra chegadas, escolhe o próximo pedido, acompanha o preparo, calcula a espera e o SLA, e mantém um histórico SQL dos eventos.

O professor aprovou o tema fast food e um grupo com sete integrantes. A apresentação está marcada para 24/11/2026. O edital exige Python com orientação a objetos, Streamlit, monitoramento visual, política contra starvation, medição de SLA, auditoria SQL, documentação, GitHub público e demonstração prática. As escolhas numéricas e as regras específicas abaixo são parâmetros do nosso cenário de simulação; não são padrões oficiais do setor.

O projeto não armazenará nomes, telefones, pagamentos nem outros dados pessoais de clientes. O pedido terá apenas um identificador fictício e dados operacionais necessários à simulação.

## 2. Regras de negócio da versão inicial

### Cenário operacional

- Há uma estação de preparo. Ela atende um pedido por vez e não interrompe um preparo iniciado.
- Pedidos podem chegar enquanto outro está sendo preparado.
- A fila mede a espera até o início do preparo. O tempo de preparo é medido separadamente.
- O relógio é simulado em segundos inteiros. Isso torna os cenários rápidos e repetíveis, sem depender de pausas reais.
- Cada pedido tem canal, complexidade, tempo de chegada e, quando aplicável, indicação de que o entregador já está aguardando.

### Prioridade

O sistema tem duas faixas:

- `URGENT`: pedido de delivery cujo entregador já chegou e aguarda a retirada.
- `STANDARD`: pedidos de balcão e retirada, além de pedidos de delivery sem entregador aguardando.

A prioridade é definida na entrada da fila e fica registrada no ticket. Na versão inicial, a chegada posterior do entregador não reclassifica tickets que já estão esperando; essa limitação mantém a regra simples e previsível.

Dentro de cada faixa, o atendimento segue FIFO: primeiro a chegar, primeiro a ser atendido.

### Política contra starvation

Usaremos uma cota rotativa: quando há pedidos nas duas faixas, podem iniciar no máximo três pedidos `URGENT` consecutivos antes de iniciar um `STANDARD`.

- Se as duas faixas têm pedidos e ainda não foram atendidos três urgentes consecutivos, inicia o mais antigo `URGENT`.
- Se três urgentes já foram iniciados e há um `STANDARD` esperando, inicia o `STANDARD` mais antigo.
- Se uma faixa estiver vazia, atende a outra.
- A contagem de urgentes fica limitada a três. Assim, se não houver `STANDARD` quando a cota completar, o próximo `STANDARD` que chegar será escolhido na próxima decisão de atendimento.
- Depois de iniciar um `STANDARD`, a contagem de urgentes consecutivos volta a zero.

A garantia demonstrável é: enquanto houver `STANDARD` esperando, a política não deixa iniciar mais de três pedidos `URGENT` antes do próximo `STANDARD`. A ordem FIFO também evita que um pedido normal seja ultrapassado por outros pedidos normais que chegaram depois dele.

### SLA e tempos de preparo

O SLA mede o tempo entre entrada na fila e início do preparo:

`espera = horário_de_início_do_preparo - horário_de_entrada_na_fila`

Metas iniciais da simulação:

- Delivery: 180 segundos (3 minutos).
- Retirada: 300 segundos (5 minutos).
- Balcão: 480 segundos (8 minutos).

Um pedido atendido dentro do limite é `CUMPRIU`; acima do limite é `EXCEDEU`. Enquanto ainda espera, pode ser marcado como `EM_RISCO` quando já consumiu pelo menos 80% do seu limite. O percentual total de cumprimento do SLA considera apenas pedidos que já começaram o preparo.

Tempos de preparo de exemplo:

- Simples: 60 segundos.
- Médio: 120 segundos.
- Complexo: 180 segundos.

Esses números são valores didáticos para a demonstração. Devem ficar configuráveis em `BusinessRules`, ser identificados no README como parâmetros simulados e aparecer no relatório com uma justificativa. Não devem ser apresentados como dados reais de restaurantes.

## 3. Classes e responsabilidades

- `Order`: dados operacionais do pedido — id, canal, complexidade, hora simulada de chegada e se o entregador está esperando.
- `Ticket`: representa o pedido dentro do fluxo — prioridade atribuída, número de chegada, estado e horários de entrada, início e conclusão.
- `OrderChannel`: enumeração com `DELIVERY`, `PICKUP` e `COUNTER`.
- `OrderComplexity`: enumeração com `SIMPLE`, `MEDIUM` e `COMPLEX`.
- `TicketStatus`: enumeração com `WAITING`, `PREPARING`, `COMPLETED` e `CANCELLED`.
- `PriorityLevel`: enumeração com `URGENT` e `STANDARD`.
- `SlaStatus`: enumeração com `WAITING`, `AT_RISK`, `MET` e `BREACHED` para separar a situação do SLA do estado do ticket.
- `BusinessRules`: atribui prioridade e fornece metas de SLA, tempos de preparo, cota de justiça e limiar de risco configuráveis.
- `PriorityQueue`: mantém uma fila FIFO por faixa, permite inserir, consultar e retirar o ticket mais antigo de uma faixa.
- `PriorityPolicy`: classe abstrata que define a interface da política que escolhe uma faixa.
- `QuotaFairnessPolicy`: implementação de `PriorityPolicy` com a cota de três urgentes para um normal.
- `SlaMonitor`: calcula a espera e classifica o cumprimento do SLA.
- `Dispatcher`: usa a fila e a política para iniciar o próximo pedido e atualizar o ticket.
- `SimulationEngine`: controla o relógio simulado, o pedido em preparo e a conclusão do preparo.
- `AuditLogger`: registra eventos e exporta um arquivo SQL executável.
- `app.py`: interface Streamlit. Chama o `SimulationEngine` e exibe resultados; não implementa regras de prioridade dentro da tela.

Relações que devem aparecer na UML:

- `Ticket` contém um `Order` (composição).
- `QuotaFairnessPolicy` herda de `PriorityPolicy`.
- `Dispatcher` usa `PriorityQueue`, `PriorityPolicy` e `SlaMonitor`.
- `SimulationEngine` coordena `Dispatcher` e `AuditLogger`.
- A camada Streamlit chama `SimulationEngine` e não acessa diretamente a fila interna.

## 4. Contratos entre os módulos

A Etapa 1 registra os nomes e as assinaturas que todos devem manter. Os métodos podem ganhar validações, mas uma etapa posterior não deve renomear interfaces sem combinar com os outros integrantes.

- `BusinessRules.priority_for(channel, courier_waiting) -> PriorityLevel`
- `BusinessRules.sla_seconds_for(channel) -> int`
- `BusinessRules.preparation_seconds_for(complexity) -> int`
- `BusinessRules.urgent_quota -> int` e `BusinessRules.at_risk_fraction -> float`
- `PriorityQueue.enqueue(ticket) -> None`
- `PriorityQueue.has_waiting(priority) -> bool`
- `PriorityQueue.pop_oldest(priority) -> Ticket`
- `PriorityQueue.snapshot() -> list[Ticket]`
- `PriorityPolicy.choose_priority(queue) -> PriorityLevel | None`
- `PriorityPolicy.record_started(priority) -> None`
- `SlaMonitor.wait_seconds(ticket, now) -> int`
- `SlaMonitor.status(ticket, now) -> SlaStatus`
- `Dispatcher.start_next(now) -> Ticket | None`
- `SimulationEngine.enqueue(order) -> Ticket` (registra a chegada no segundo simulado atual).
- `SimulationEngine.advance(seconds) -> SimulationSnapshot` (avança o relógio e processa conclusões de preparo).
- `AuditLogger.record(event) -> None`
- `AuditLogger.export_sql() -> str`

`QueueEvent` é imutável e descreve o ticket, tipo/instante do evento, canal, prioridade, tamanho da fila antes/depois, snapshot dos tickets ainda esperando e dados de SLA opcionais. O snapshot contém os IDs da fila após o evento e seu tamanho deve coincidir com `queue_size_after`. O módulo de serviços emite esses eventos tipados. Assim, a Etapa 5 consegue funcionar com a interface `AuditLogger` antes de a Etapa 6 implementar a gravação SQLite; a Etapa 7 conecta a implementação concreta.

## 5. Estrutura sugerida do repositório

```text
app.py
README.md
pyproject.toml
src/fastfood/
  domain/
    enums.py
    order.py
    ticket.py
    rules.py
    events.py
  queues/
    priority_queue.py
    priority_policy.py
  services/
    sla_monitor.py
    dispatcher.py
    simulation_engine.py
  audit/
    audit_logger.py
sql/
  schema.sql
exports/
tests/
docs/
  planejamento.md
  modelagem.md
  dicionario.md
README.md
requirements.txt
.gitignore
```

Usaremos `collections.deque` para as faixas FIFO, `dataclasses` e `Enum` para o domínio, `sqlite3` para SQL e `unittest` para testes. Streamlit é a biblioteca externa principal. A escolha de duas filas FIFO com política rotativa forma uma fila de múltiplos níveis; o relatório deve explicar essa estrutura e suas complexidades: inserir e retirar de uma faixa custam O(1), escolher entre as duas faixas custa O(1), e montar um retrato completo da fila custa O(n).

## 6. Divisão sequencial em sete etapas

Cada integrante é responsável pelo código e pela explicação da sua etapa. A pessoa seguinte só começa depois da revisão e integração da etapa anterior à `main`.

### Etapa 1 — Cenário, regras, contratos e base do projeto

**Responsável:** Integrante 1.

**Fazer:** formalizar cenário e regras; criar a estrutura inicial; definir enums; implementar `BusinessRules`; escrever as interfaces públicas; produzir o diagrama de classes inicial e o dicionário de dados/métodos.

**Arquivos principais:** `docs/escopo.md`, `docs/modelagem.md`, `docs/dicionario.md`, `src/fastfood/domain/enums.py`, `src/fastfood/domain/rules.py`, `src/fastfood/domain/events.py`.

As regras recebem `channel`, `courier_waiting` e `complexity` como valores simples. Assim, a Etapa 1 pode implementar `BusinessRules` sem depender da classe `Order`, que só será criada na Etapa 2.

**Aceite para a Etapa 2:** os sete integrantes aprovam prioridade, cota, metas de SLA, tempos simulados e contratos; regras podem ser verificadas por testes unitários.

**A pessoa precisa explicar:** diferença entre requisito do edital e hipótese da simulação; por que o delivery com entregador aguardando é urgente; o que o SLA mede.

### Etapa 2 — Pedido, ticket e estados

**Responsável:** Integrante 2.

**Fazer:** implementar `Order` e `Ticket`; validar canal, complexidade e horários; atribuir id e sequência de chegada; implementar transições permitidas entre estados; garantir que a prioridade do ticket use `BusinessRules`.

**Arquivos principais:** `domain/order.py`, `domain/ticket.py` e testes do domínio.

**Aceite para a Etapa 3:** tickets podem ser criados sem dados inválidos; timestamps e estados têm comportamento coberto por testes; o ticket mantém sua relação com o pedido.

**A pessoa precisa explicar:** por que `Order` e `Ticket` são objetos diferentes; quais dados cada um possui; como e por que um estado pode mudar.

### Etapa 3 — Estrutura da fila

**Responsável:** Integrante 3.

**Fazer:** implementar as faixas `URGENT` e `STANDARD` usando uma `deque` por faixa; adicionar inclusão, consulta, retirada do mais antigo e `snapshot`; rejeitar prioridade desconhecida e remoção de fila vazia com erro compreensível.

**Arquivo principal:** `queues/priority_queue.py`.

**Aceite para a Etapa 4:** testes comprovam FIFO dentro de cada faixa, contagem correta, consulta das duas faixas e preservação do estado ao gerar `snapshot`.

**A pessoa precisa explicar:** por que há duas faixas; por que `deque` serve para FIFO; o significado de O(1) e O(n) neste módulo.

### Etapa 4 — Política de justiça

**Responsável:** Integrante 4.

**Fazer:** implementar `PriorityPolicy` e `QuotaFairnessPolicy`; manter o contador de urgentes consecutivos; consultar as faixas disponíveis; escolher a próxima sem retirar o ticket da fila; atualizar o contador quando o atendimento realmente começa.

**Arquivo principal:** `queues/priority_policy.py`.

**Aceite para a Etapa 5:** teste com um normal e uma sequência longa de urgentes prova que o normal inicia depois de, no máximo, três inícios urgentes enquanto aguarda. Testes cobrem também uma faixa vazia e a reinicialização do contador.

**A pessoa precisa explicar:** como a regra evita starvation; o que ela garante e o que não garante; por que prioridade não significa exclusão permanente da outra faixa.

### Etapa 5 — Serviço, simulação e SLA

**Responsável:** Integrante 5.

**Fazer:** implementar `SlaMonitor`, `Dispatcher` e `SimulationEngine`; obter a prioridade selecionada pela política; mover o ticket para `PREPARING`; calcular espera e SLA; avançar o relógio até o fim do preparo; permitir novas chegadas durante uma simulação; emitir eventos tipados para a interface de auditoria.

**Arquivos principais:** `services/sla_monitor.py`, `services/dispatcher.py`, `services/simulation_engine.py`, `domain/events.py`.

**Aceite para a Etapa 6:** um cenário pequeno percorre entrada, espera, início e conclusão; resultados de espera e SLA batem com os horários simulados; um pedido não começa antes de a estação ficar livre.

**A pessoa precisa explicar:** a fórmula da espera; por que o relógio é simulado; diferença entre tempo de espera e tempo de preparo; como o sistema sinaliza cumprimento, risco e excesso do SLA.

### Etapa 6 — Auditoria SQL

**Responsável:** Integrante 6.

**Fazer:** implementar `AuditLogger` com `sqlite3`; gravar pelo menos `ENQUEUED` e `SERVICE_STARTED`, além de conclusão; usar transação por evento; gravar tamanho da fila antes/depois e um snapshot JSON dos tickets à espera; criar exportação com `INSERT` executáveis.

**Arquivos principais:** `audit/audit_logger.py`, `sql/schema.sql`, exportação `exports/logs.sql`.

**Campos mínimos do evento:** id do evento, id do ticket, tipo, segundo simulado, canal, prioridade, tamanho da fila antes/depois, espera quando conhecida, alvo do SLA, resultado do SLA e snapshot da fila.

**Aceite para a Etapa 7:** iniciar um banco pelo `schema.sql`, executar o `logs.sql` exportado e recuperar a sequência dos eventos sem alterar o histórico. O aplicativo não apaga nem atualiza eventos existentes.

**A pessoa precisa explicar:** o que uma transação protege; por que o log é append-only; como o SQL exportado permite reproduzir o histórico.

### Etapa 7 — Streamlit, integração e demonstração

**Responsável:** Integrante 7.

**Fazer:** criar formulários de pedido; preservar o estado da simulação entre atualizações da página; exibir fila por prioridade, pedido em preparo, relógio, espera, estado do SLA e histórico; permitir avançar a simulação; incluir um botão de exportação SQL; finalizar README e roteiro de demonstração.

**Arquivos principais:** `app.py`, `README.md`, `requirements.txt`, testes do fluxo completo.

**Aceite final:** outra pessoa consegue instalar e executar pelo README; a interface mostra chegadas e atendimentos; o teste de estresse mostra a cota de justiça funcionando; o SLA é calculado; o histórico SQL exportado é executável.

**A pessoa precisa explicar:** caminho dos dados da tela até o domínio; como o estado é preservado no Streamlit; como a demonstração comprova cada requisito.

## 7. Protocolo de trabalho e commits

1. O integrante escolhe a etapa depois de ler sua descrição. Recomendo que cada pessoa indique três preferências para facilitar o acordo.
2. A pessoa abre uma branch própria, por exemplo `feat/01-business-rules`, e trabalha apenas nos arquivos da sua etapa.
3. Ao terminar, roda os testes da etapa, atualiza sua documentação e abre uma PR.
4. A pessoa da etapa seguinte revisa a PR anterior. Ela só inicia código depois que a PR for aprovada e integrada à `main`.
5. Cada integrante usa sua própria conta GitHub e faz commits pequenos com mudanças reais. Não usar uma conta compartilhada nem squash merge, para manter os commits individuais visíveis.
6. Após cada integração, todos leem o resumo de handoff e executam os testes antes de iniciar a etapa seguinte.

Uma etapa só está concluída quando seus critérios de aceite passaram, a documentação correspondente está atualizada, a PR foi integrada e o responsável consegue explicar o código sem consultar a resposta de uma IA.

## 8. Perguntas de ensaio individual

- **Integrante 1:** Quais regras são hipóteses da simulação? Como elas foram configuradas?
- **Integrante 2:** Qual é a diferença entre um pedido e um ticket? Quais transições de estado são válidas?
- **Integrante 3:** Como a fila mantém FIFO por prioridade? Qual o custo de inserir e retirar?
- **Integrante 4:** Qual sequência prova que um pedido normal não sofre starvation? Qual é o limite garantido?
- **Integrante 5:** Como o sistema calcula a espera? Como um SLA passa de em risco para excedido?
- **Integrante 6:** Quais eventos entram no SQL? Como a transação e o arquivo exportado preservam a auditoria?
- **Integrante 7:** Como um pedido percorre a interface, a simulação e o histórico? Como reproduzir a demonstração?

## 9. Requisitos do edital a conferir na entrega

- Relatório com problema, regras de negócio e justificativa do algoritmo.
- UML com atributos, métodos, modificadores, composição e herança.
- Dicionário de classes, métodos e estruturas de dados.
- POO em Python e interface Streamlit funcional.
- Visualização da fila, dos atendimentos e do histórico.
- Teste de estresse que demonstra a política de justiça e métricas de SLA.
- Auditoria SQL de entrada e atendimento, com `schema.sql` e exportação executável `logs.sql`.
- Repositório público com commits distribuídos e README de execução.
- Apresentação de 20 minutos: 3 minutos de pitch, 7 minutos de demonstração e 10 minutos de arguição individual.
