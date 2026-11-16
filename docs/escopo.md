# Escopo e regras vigentes — Etapa 7

KitchenFlow simula uma cozinha de fast food com uma estação não preemptiva, canais balcão, retirada e delivery, fila de prioridade e relógio inteiro em segundos. Tema e sete integrantes autorizados pelo professor. As regras foram confirmadas pelo grupo e agora são configuráveis no laboratório.

## Requisitos e hipóteses

O edital exige POO, política para mitigar starvation, acompanhamento de SLA e logs SQL íntegros; para a stack Python escolhida pelo grupo, exige Streamlit. Uma estação, cota 3, urgência de delivery com entregador presente, metas 180/300/480 s, preparos 60/120/180 s e risco em 80% são hipóteses didáticas configuráveis, não medições reais.

## Contratos temporais

1. Um pedido entra no segundo atual, recebe ID exclusivo, prioridade e configuração de admissão.
2. A fila é FIFO dentro de cada faixa. `snapshot()` agrupa urgentes e padrão; não prevê toda a ordem de despacho.
3. Até a cota de urgentes consecutivos, escolhe-se urgente; atingida a cota e havendo padrão, escolhe-se o padrão mais antigo. Iniciar padrão zera o contador. Se só existem urgentes, o contador satura na cota.
4. O primeiro início ocorre ao avançar um segundo. Conclusão e próximo início podem ocorrer no mesmo segundo, em ordem de registro.
5. SLA = início − entrada; o tempo de preparo não integra a espera. Antes do início, >= limiar é risco e > meta é excesso. Após início, <= meta cumpre.
6. Metas/prioridades novas só afetam novas chegadas. Durações novas afetam próximos inícios. Cota e limiar de alerta têm efeito imediato. Resultados históricos não mudam.
7. Pausar cozinha suspende produção, não o relógio. Ajustar preparo redefine o restante. Cancelar só é permitido na espera.
8. Cada mudança relevante gera evento ou ação SQL. Falha na persistência desfaz também a mudança em memória.

## Limites e evidências

Uma oportunidade para padrão a cada cota não garante cumprir SLAs sob qualquer volume, nem espera fixa para cada pedido padrão. Há fila interna entre padrões. Pausas e mudanças adversariais podem prolongar a espera. A interface limita lotes a 200, fila a 2000 aguardando e avanço a 86400 s por comando.

O histórico é durável por sessão em `data/`. O motor fica em memória; não há restauração automática de execução. São usados IDs fictícios sem dados pessoais. Pagamentos, entregas físicas, múltiplas estações e autenticação estão fora do recorte.

Consulte [README](../README.md), [arquitetura completa](../entregas/final/diagrama_completo.md) e [validação](validacao.md). O planejamento original permanece como registro da divisão entre integrantes.
