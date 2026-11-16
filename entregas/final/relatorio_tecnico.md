# KitchenFlow — Relatório técnico final

**Projeto A3 — Filas de Prioridade · Python, Orientação a Objetos e Auditoria SQL**  
**Versão:** integração das sete etapas, revisada em 16/11/2026.  
**Equipe:** sete integrantes, conforme autorização do professor informada pelo grupo.  
**Repositório:** https://github.com/JeffRosaDev/projeto_a3_sergio

## 1. Problema e contexto

Uma cozinha recebe pedidos de balcão, retirada e delivery e compartilha capacidade de preparo. No cenário adotado, um entregador já presente aumenta a urgência operacional do delivery: além do cliente, existe outro profissional aguardando a liberação. Prioridade absoluta a esses pedidos, porém, pode adiar indefinidamente os pedidos comuns quando novas urgências chegam continuamente.

KitchenFlow é um laboratório para observar esse conflito, experimentar regras e explicar decisões. Representa uma estação de preparo não preemptiva: depois de iniciado, um pedido não é trocado por outro mais urgente. Interrupções físicas podem suspender o trabalho e mudanças de duração podem representar lentidão ou recuperação. Não há pagamentos, dados reais de clientes ou integrações comerciais.

## 2. Requisitos e decisões de modelagem

O edital disponibilizado, *A3 — Projeto Semestral — Filas de Prioridade*, pede modelagem OO, mecanismo contra starvation, métricas de SLA, logs SQL de entrada/saída, repositório público, README, UML e dicionário de classes/métodos. Para a stack Python escolhida pelo grupo, a interface requerida é Streamlit. A escolha de fast food e a equipe de sete foram autorizadas pelo docente, segundo a confirmação do grupo.

Uma estação, duas faixas, cota inicial de três urgentes, metas em segundos e durações determinísticas são hipóteses de simulação. Não são valores impostos pelo edital nem medições de restaurantes. IA foi autorizada pelo professor conforme informado pelo grupo; a explicação individual das decisões continua sendo responsabilidade de cada integrante.

## 3. Regras de negócio

Cada pedido possui ID único na sessão, canal, complexidade, instante de chegada e indicação de entregador aguardando. Sua admissão cria um Ticket com prioridade, sequência e configuração de SLA preservadas.

1. Delivery com entregador presente entra como urgente quando essa regra está habilitada; os demais entram na faixa padrão.
2. A fila é FIFO dentro de cada faixa. Uma política de cota escolhe a faixa; a fila fornece seu pedido mais antigo.
3. Com padrões aguardando, após até três inícios urgentes a próxima oportunidade é do padrão mais antigo. O valor três é configurável. Se uma faixa estiver vazia, a outra continua atendida.
4. SLA mede espera até o início do preparo, não o prazo total de entrega. Metas iniciais: delivery 180 s, retirada 300 s e balcão 480 s.
5. Preparos simples, médios e complexos duram inicialmente 60, 120 e 180 s. O alerta começa em 80% da meta; espera acima da meta caracteriza excesso. Início exatamente na meta cumpre o SLA.
6. A primeira decisão ocorre no segundo seguinte ao avanço; ao concluir um pedido, outro pode começar no mesmo segundo.
7. Pausa da cozinha suspende produção e mantém espera crescente quando o relógio avança. Pausa da reprodução congela o relógio. Ajuste de restante substitui o tempo restante do preparo ativo.
8. Apenas pedidos aguardando podem ser cancelados. O registro e o ID continuam no histórico.

Alterações de SLA e urgência afetam novas admissões; durações afetam próximos inícios; cota e limiar de alerta têm efeito imediato. Uma duração ativa só muda por intervenção explícita. Assim, o laboratório permite experimentar sem reescrever o significado dos resultados já registrados.

## 4. Estratégia de solução e justificativa

A estrutura usa duas deques e um conjunto de IDs. Para duas faixas fixas, isso oferece FIFO claro e inserção/retirada das pontas com custo esperado O(1), sem ordenar todos os pedidos. O conjunto evita duplicidade entre aguardando; o registro do motor reserva IDs durante toda a sessão.

A política por cota foi escolhida pela facilidade de demonstrar justiça: ela limita urgentes consecutivos entre oportunidades da faixa padrão. O contador só muda com início efetivo e satura quando só existem urgentes. Uma nova chegada padrão encontra a oportunidade já devida, sem reiniciar a contagem. Alterar a cota preserva o acumulado, limitado ao novo máximo.

O mecanismo mitiga starvation sob operação contínua e durações finitas. Ele não garante que todo ticket padrão espere no máximo três preparos, pois outros padrões podem estar à frente. Também não cria capacidade para cumprir qualquer SLA sob sobrecarga. O sistema mede excessos, permite experimentar capacidade/chegadas e evidencia condições em que a meta é inviável; não promete garantia comercial universal.

Snapshots e checkpoints custam O(n); portanto, o despacho completo com auditoria não é anunciado como O(1). O motor salta até eventos relevantes quando possível, evitando percorrer cada segundo de um intervalo ocioso. A interface automática intercala chegadas no relógio simulado.

## 5. Arquitetura orientada a objetos

O domínio contém enums, BusinessRules, Order, Ticket e QueueEvent. Order representa dados imutáveis de entrada; Ticket contém Order por composição e representa o ciclo de vida. BusinessRules preserva configurações; QueueEvent representa fatos imutáveis.

PriorityPolicy é uma classe abstrata; QuotaFairnessPolicy concretiza o contrato por herança. Dispatcher recebe fila, política, monitor de SLA e auditoria por injeção. SimulationEngine coordena relógio e estação única. AuditLogger encapsula SQLite. Streamlit apresenta estado e encaminha comandos aos serviços, sem duplicar a política no código visual.

As sete etapas permanecem rastreáveis: base/regras; pedido/ticket; filas; política; serviços; auditoria; interface/integração. O histórico Git dos integrantes foi preservado. A integração final contém alterações necessárias em várias camadas, porque regras dinâmicas e recuperação transacional atravessam esses contratos.

Consulte o [UML e diagramas completos](diagrama_completo.md), a [versão visual offline](diagrama_completo.html) e o [dicionário detalhado](../../docs/dicionario.md) para atributos, métodos, visibilidade, estados, relações e complexidades.

## 6. Auditoria e recuperação de erros

`queue_events` registra entradas, inícios, conclusões e cancelamentos, com contagens antes/depois e IDs da fila posterior. `simulation_actions` registra configuração e incidentes. `audit_sequence` fornece ordem global, inclusive para eventos e ações ocorridos no mesmo segundo.

Savepoints SQLite e checkpoints de memória compõem uma unidade recuperável: se a gravação falha, relógio, tickets, fila e política retornam ao estado anterior. IDs de evento impedem duplicidade; triggers bloqueiam UPDATE/DELETE usuais. Esses mecanismos protegem consistência operacional, mas não são defesa criptográfica contra um administrador que altere schema/arquivo.

O SQL exportado inclui schema, dados, timestamps originais e sequência de inserção; deve ser importado em banco vazio. Cada sessão Streamlit usa banco próprio em data. Logs persistem em disco, mas o motor em memória não é automaticamente reconstituído após perda da sessão.

## 7. Interface e experimentação

O painel apresenta relógio, indicadores gerais e por canal, estação ativa, tempo restante, faixas, espera, risco e faixa elegível. O laboratório permite editar SLA, durações, cota, alerta e urgência; pausar a cozinha; ajustar preparo ativo; cancelar pedidos aguardando. Há reprodução automática, chegadas periódicas, lotes com semente reproduzível, histórico e download SQL.

Os controles distinguem execução visual de disponibilidade física. Inputs têm limites didáticos: até 200 pedidos por lote, 2000 simultaneamente aguardando e 86400 s por avanço. Reiniciar exige confirmação na interface, mantém o banco anterior e abre outra sessão. Erros esperados são apresentados em texto; uma falha automática interrompe a reprodução e mantém seu motivo visível.

## 8. Validação e resultados

A revisão local executou 64 testes automatizados cobrindo domínio, filas, cota, SLA, transações, exportação e widgets Streamlit. Foram incluídas 350 operações pseudoaleatórias, 100 urgentes com padrão aguardando, limites exatos de SLA, duplicidades, alterações em execução, falhas SQL após INSERT e entre conclusão/início, isolamento de sessões e gravações concorrentes no logger. Ruff não identificou infrações nas regras configuradas.

O teste de navegador em Edge headless verificou desktop e celular, abas, cenário, despacho, reprodução e download SQL. O arquivo baixado foi reimportado. Isso não constitui prova de ausência de todos os erros nem teste de todos os dispositivos.

Em três experimentos com os mesmos 40 pedidos simultâneos e semente 42, todos concluíram. Na condição padrão, 10% iniciaram no SLA e a espera média foi 2123,5 s. Com durações dobradas, 7,5% cumpriram e a média foi 4246 s. Com pausa inicial de 300 s, nenhum iniciou no SLA e a média foi 2423,5 s. O pico foi deliberadamente superior à capacidade; os resultados demonstram a diferença entre justiça e capacidade, sem estimar desempenho comercial real.

Os comandos e os limites da validação estão no [README](../../README.md) e nas [evidências](../../docs/validacao.md). O script [simulate.py](../../scripts/simulate.py) gera [resultados JSON](../../exports/cenarios.json) e [SQL de exemplo](../../exports/logs.sql). O workflow do repositório executa testes em Python 3.11, 3.12 e 3.13 a cada push/PR.

## 9. Demonstração e responsabilidades

O roteiro acompanha o edital: pitch de três minutos, demonstração de sete e arguição individual de dez. O grupo pode demonstrar a sequência urgente/urgente/urgente/padrão, modificar tempos, mostrar pausa e excesso de SLA, retomar operação e exportar a trilha SQL. Cada integrante deve conseguir explicar os contratos de sua etapa, as interações com as demais e o resultado dos testes.

Use os [slides finais](kitchenflow_apresentacao.pptx) e o [roteiro detalhado](roteiro.md). A solução entregue é um protótipo acadêmico funcional de uma cozinha. Validação com dados reais, múltiplas estações, autenticação, restauração da execução e implantação comercial seriam trabalhos posteriores.

## Referências do projeto

- Edital fornecido pelo professor: `A3__Projeto_Semestral__Filas_de_Prioridade_20261006192851.pdf`, duas páginas; critérios e roteiro de apresentação.
- [Planejamento das sete etapas](../../docs/planejamento.md) e [escopo vigente](../../docs/escopo.md).
- Código, testes e histórico do repositório público indicado na identificação deste relatório.
