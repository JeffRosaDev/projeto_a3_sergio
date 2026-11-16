# Modelagem final

O diagrama completo está em [entregas/final/diagrama_completo.md](../entregas/final/diagrama_completo.md), com UML, arquitetura, estados, sequência transacional e modelo SQL. A [versão visual](../entregas/final/diagrama_completo.html) abre no navegador.

Todas as sete etapas estão implementadas. A fonte atual usa `Ticket.sequence`, `started_at`, `start_preparation()` e `complete_preparation()`; o motor usa `current_time`. Consulte o diagrama para os atributos e modificadores atuais, incluindo regras dinâmicas e auditoria de intervenções.

`Ticket` contém `Order` e preserva `BusinessRules` da admissão. `QuotaFairnessPolicy` implementa `PriorityPolicy`; `Dispatcher` colabora com fila, política, SLA e auditoria. O motor coordena o relógio e checkpoints. O Streamlit chama os serviços e mantém uma sessão por navegador.
