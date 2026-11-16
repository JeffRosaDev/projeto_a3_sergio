# Roteiro da apresentação final

## Pitch — 3 minutos

Apresente KitchenFlow como laboratório de decisões para uma cozinha: enxergar a fila, experimentar hipóteses e explicar cada atendimento. Não prometa ganhos comerciais medidos. O protótipo é acadêmico, com uma estação, sem dados de clientes reais. Explique a tensão entre urgência, justiça e capacidade.

## Demonstração — 7 minutos

1. Sessão vazia, padrões 180/300/480, preparos 60/120/180, cota 3.
2. Carregue Justiça 3:1 (7 pedidos). +1 s inicia PED-0002; três passos de +60 s levam o padrão PED-0001 ao início em 181 s.
3. Aumente preparo simples para 180 s. A mudança afeta próximos inícios; o preparo ativo mantém prazo.
4. Reduza SLA de delivery para 60 s e adicione novos deliveries. Compare metas dos antigos e novos.
5. Pause a cozinha e avance 180 s. A espera cresce, a produção não. Retome e ajuste restante do preparo para 10 s.
6. Cancele um aguardando. Abra Histórico e mudanças de regras. Baixe o SQL e mostre a ordem global e os registros.
7. Mostre experimento de 40 chegadas simultâneas. Explique por que justiça não cria capacidade nem garante todo SLA.

## Arguição individual — 10 minutos

1. Base: requisito do edital versus hipótese; configuração imutável versus nova versão de regras.
2. Domínio: Order versus Ticket, composição, transições válidas e timestamps.
3. Filas: duas deques, FIFO por faixa, snapshot agrupado não é previsão de despacho.
4. Justiça: contador satura; política escolhe sem retirar; herança; garantia entre oportunidades de padrões.
5. Serviços: espera congela no início; motor salta eventos; pausa física versus reprodução; rollback em memória.
6. Auditoria: savepoints, chave primária, JSON, sequência global, triggers e limites de append-only.
7. UI: session_state, fragmentos, formulários, inputs limitados, sessões isoladas, exportação e testes.

## Antes de apresentar

Instale pelo README, abra o aplicativo e confira o projetor. Use uma sessão nova. Execute os testes antes do ensaio. Deixe o PPTX, o diagrama HTML offline e o SQL acessíveis. A conexão à internet não é necessária depois de instalar as dependências. Não apresente o fluxo como sistema comercial já implantado.
