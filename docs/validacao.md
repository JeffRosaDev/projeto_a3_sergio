# Validação da Etapa 7

Executada em 15–16/11/2026, Windows, Python 3.13 e Streamlit 1.67.0. Os comandos reproduzíveis estão no README. O teste automatizado não elimina todos os possíveis defeitos; estas são as verificações realmente feitas.

- 64 testes unitários, de integração e AppTest passaram na execução local.
- Ruff: nenhuma infração nas regras configuradas E4/E7/E9/F.
- 350 operações pseudoaleatórias com semente fixa: inclusão, avanço, cota, pausa e cancelamento; verificação de unicidade, estados e estação única após cada ação.
- Cota com 100 urgentes, cota alterada durante preparo e atendimento de padrão após saturação.
- Limiares exatos 143/144/180/181 s para delivery; início em t=0; espera congelada após início.
- Rejeição de IDs duplicados, chegada futura, cancelamento de inexistente/em preparo, avanço negativo, booleano, fracionário e além do limite.
- Falhas SQL injetadas depois de INSERT e entre conclusão/início: memória, relógio, contador e registros restaurados.
- SQL exportado reimportado: igualdade de todos os campos, recorded_at e sequência global; UPDATE e DELETE bloqueados por triggers.
- 50 ações de auditoria gravadas a partir de threads distintas com conexão serializada.
- AppTest: criar, repetir ID, avançar, cenário, alterar parâmetros, pausar, ajustar preparo, retomar, reiniciar com confirmação e preservar o motivo da parada após falha na reprodução automática.
- Navegador Edge headless: desktop 1440×1000 e celular 390×844; cenário, despacho, abas, reprodução automática e download de SQL; nenhum stException visível.

## Experimentos comparáveis

`scripts/simulate.py` aplica os mesmos 40 pedidos simultâneos (semente 42) a três condições. Valores completos em `exports/cenarios.json`.

- Padrão: 40 concluídos; 10% dos inícios no SLA; espera média 2123,5 s.
- Preparo com duração dobrada: 40 concluídos; 7,5% no SLA; espera média 4246 s.
- Pausa inicial de 300 s: 40 concluídos; 0% no SLA; espera média 2423,5 s.

É uma sobrecarga deliberada. A política mantém oportunidades de atendimento; não cria capacidade de produção. Esses números são evidência da simulação e não métricas comerciais.

## Limitações conhecidas

Revisão da interface e auditoria em 16/11: 73 testes locais aprovados, incluindo acumulação do relógio entre redraws frequentes, retomada após pausa, limite de recuperação, rollback de chegadas automáticas e trilha global de eventos/comandos. O script opcional `scripts/check_browser.py` verifica reprodução, foco e rascunho de formulário durante atualização, pausas, incidentes, duplicidade, download/importação SQL e sessão mobile isolada.

O teste visual não representa todos os navegadores/dispositivos. A reprodução automática depende da aba aberta e não pretende medir tempo real com precisão. SQL preserva o histórico, não retoma o motor. O limite de 2000 é de pedidos simultâneos aguardando; sessões prolongadas acumulam eventos e podem consumir memória/disco. Bancos locais devem ser geridos pelo responsável. A avaliação de SLA não é certificação de garantia comercial.
