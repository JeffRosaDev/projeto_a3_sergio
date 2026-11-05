# Escopo e regras de negócio

**Projeto:** sistema de filas de prioridade para fast food  
**Etapa:** 1 — cenário, regras, contratos e base do projeto  
**Situação:** proposta inicial para leitura e validação pelos sete integrantes.

## 1. Enunciado

Uma cozinha de fast food recebe pedidos por balcão, retirada e delivery durante um período de movimento intenso. Todos aguardam uma estação de preparo que só consegue iniciar um pedido por vez. O grupo implementará uma simulação orientada a objetos que organiza esses pedidos, escolhe qual deve começar, mede o tempo de espera e registra os eventos necessários para reconstituir o atendimento.

Pedidos de delivery podem exigir prioridade operacional quando o entregador já está aguardando. A fila não pode deixar que a prioridade urgente impeça indefinidamente o atendimento de pedidos comuns. A simulação também deve sinalizar o cumprimento ou excesso dos limites de espera definidos para cada canal e produzir dados de auditoria consistentes.

## 1.1 Requisitos do projeto e hipóteses do cenário

| Origem | Definição | Como explicar na apresentação |
|---|---|---|
| Edital do professor | Solução orientada a objetos para uma fila de prioridade; mitigar starvation; acompanhar SLAs; manter integridade dos logs. | São os objetivos obrigatórios da solução, independentemente do tema escolhido. |
| Tema aprovado para o grupo | Simular pedidos de uma operação de fast food. | É o contexto escolhido pelo grupo e autorizado pelo professor. |
| Hipóteses da simulação | Uma estação; delivery urgente quando o entregador aguarda; cota de três urgentes; metas de SLA; tempos de preparo; risco em 80%. | São valores controláveis para construir cenários repetíveis, não regras do edital nem dados reais do setor. |

## 2. Problemática

Uma regra que sempre escolhe o pedido de maior prioridade pode deixar pedidos comuns esperando sem limite quando novos urgentes continuam chegando. Ao mesmo tempo, atender simplesmente pela ordem global de chegada ignora entregadores que já aguardam e pode aumentar atrasos operacionais. Sem timestamps e histórico de eventos, também fica difícil explicar por que um ticket foi atendido naquela ordem ou verificar se o limite de espera foi respeitado.

## 3. Justificativa da solução

O projeto separa pedidos urgentes e padrão, preserva FIFO em cada faixa e aplica uma cota rotativa entre as faixas. Essa combinação permite priorizar entregadores presentes sem permitir uma sequência ilimitada de urgentes enquanto existir um pedido padrão aguardando. Um relógio simulado torna os mesmos cenários rápidos e reproduzíveis. Um monitor de SLA mede a espera separadamente do tempo de preparo. Eventos tipados deixam a auditoria desacoplada da interface e permitem persistência e exportação SQL em etapa posterior.

## 4. Limite do cenário

- Uma única estação inicia um pedido por vez; um preparo que começou não é interrompido.
- Pedidos podem chegar enquanto outro está em preparo.
- A espera do SLA começa quando o ticket entra na fila e termina quando o preparo começa.
- O tempo de preparo é contabilizado separadamente da espera.
- O relógio avança em segundos simulados inteiros, sem pausas reais.
- A versão inicial não inclui pagamentos, cadastro de clientes, nomes, telefones, roteirização de entregas ou várias estações paralelas.
- São usados apenas identificadores fictícios e dados operacionais necessários à simulação.

## 5. Regras de negócio

### 5.1 Canais e prioridade

Há três canais: `DELIVERY`, `PICKUP` e `COUNTER`.

- Um pedido `DELIVERY` é `URGENT` se, e somente se, o entregador já estiver aguardando no momento em que o ticket entra na fila.
- Todo pedido `PICKUP` ou `COUNTER` é `STANDARD`.
- Um pedido `DELIVERY` sem entregador aguardando também é `STANDARD`.
- A prioridade é calculada na entrada e fica registrada no ticket. Na primeira versão, a chegada posterior do entregador não reclassifica tickets que já aguardam.
- Dentro de cada nível, vale FIFO: o ticket mais antigo daquela faixa é considerado primeiro.

### 5.2 Cota contra starvation

Quando as duas faixas têm pedidos esperando, a política pode iniciar no máximo **três `URGENT` consecutivos** antes de iniciar o ticket `STANDARD` mais antigo.

1. Se as duas faixas estão ocupadas e a cota ainda não foi atingida, inicia o `URGENT` mais antigo.
2. Se três urgentes já começaram e há um `STANDARD` aguardando, inicia o `STANDARD` mais antigo.
3. Se uma faixa está vazia, inicia pela faixa que ainda tem pedidos.
4. A contagem de urgentes satura em três quando não há `STANDARD` para atender. O próximo `STANDARD` que chegar será escolhido na decisão de atendimento seguinte.
5. Depois que um `STANDARD` começa, a contagem consecutiva de urgentes volta a zero.

**Garantia delimitada:** enquanto houver um `STANDARD` esperando, não começam mais de três `URGENT` antes do próximo `STANDARD`. A regra não garante que todo SLA será cumprido sob qualquer taxa de chegada: uma carga maior que a capacidade da estação ainda pode provocar violações, que serão registradas e medidas.

### 5.3 Metas de SLA

O SLA mede o intervalo entre entrada na fila e início do preparo:

`espera_em_segundos = início_do_preparo - entrada_na_fila`

| Canal | Meta simulada para iniciar o preparo |
|---|---:|
| `DELIVERY` | 180 s (3 min) |
| `PICKUP` | 300 s (5 min) |
| `COUNTER` | 480 s (8 min) |

- Antes do início, o ticket está `WAITING` ou `AT_RISK`.
- Enquanto aguarda, fica `AT_RISK` após consumir pelo menos 80% da meta.
- Ao iniciar, fica `MET` se a espera for menor ou igual à meta; caso contrário, `BREACHED`.
- O percentual de cumprimento considera somente tickets que já iniciaram o preparo.
- Os limites são parâmetros da simulação, não compromissos observados de uma operação real.

### 5.4 Complexidade e duração simulada

| Complexidade | Duração de preparo simulada |
|---|---:|
| `SIMPLE` | 60 s |
| `MEDIUM` | 120 s |
| `COMPLEX` | 180 s |

Esses valores servem para construir cenários verificáveis. Devem ser configuráveis em `BusinessRules` sem alterar a lógica de despacho.

## 6. Responsabilidades do sistema

1. Receber dados operacionais de um pedido e classificar sua prioridade com `BusinessRules`.
2. Guardar os tickets em faixas FIFO independentes.
3. Escolher a faixa de atendimento respeitando a cota de justiça.
4. Medir espera e situação do SLA em cada decisão de atendimento.
5. Controlar o relógio simulado e a ocupação da estação.
6. Emitir eventos tipados para entrada, início do serviço, conclusão e cancelamento.
7. Em etapas posteriores, persistir eventos com SQLite, exportar SQL executável e exibir fila e indicadores em Streamlit.

## 7. Fora de escopo nesta etapa

Não estão sendo implementados agora os objetos `Order` e `Ticket`, a estrutura de filas, a política de justiça, o despacho, o motor, a persistência SQLite, o aplicativo Streamlit nem o teste de estresse. Eles pertencem às etapas sequenciais seguintes. Esta etapa estabelece seus contratos e o vocabulário compartilhado.

## 8. Critérios de aceite da Etapa 1

- Escopo, cenário, regras, hipóteses numéricas e garantias estão documentados.
- Os enums e as assinaturas compartilhadas têm nomes únicos e coerentes.
- `BusinessRules` calcula prioridade e fornece tempos de SLA e preparo configuráveis.
- O evento tipado registra os dados operacionais mínimos para futuras etapas de auditoria.
- O diagrama inicial e o dicionário descrevem as classes planejadas sem afirmar que já foram implementadas.
- Os testes unitários verificam a prioridade, a normalização de valores simples, os parâmetros e a consistência de `QueueEvent`.
- Os sete integrantes revisam as regras antes de iniciar a Etapa 2.

## 9. Decisões que o grupo deve confirmar

- Os três níveis e as metas de SLA propostos.
- A definição de delivery urgente baseada na presença do entregador.
- A cota de três urgentes consecutivos.
- Uma estação, atendimento não preemptivo e relógio em segundos simulados.
- Os tempos de preparo por complexidade.

Se o grupo alterar esses parâmetros, atualize este documento, `BusinessRules` e o diagrama antes de iniciar a etapa dependente.
