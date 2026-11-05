# Sistema de filas de prioridade para fast food

Projeto acadêmico de Algoritmos e Programação Orientada a Objetos. O grupo vai construir uma simulação de fila para pedidos de fast food, com prioridade, proteção contra starvation, acompanhamento de SLA, auditoria SQL e interface Streamlit.

## Estado atual

O repositório está na **Etapa 1 — cenário, regras, contratos e base do projeto**. Nesta etapa, estão sendo fixados o escopo e as interfaces de domínio que as etapas seguintes usarão. A aplicação Streamlit e o motor completo ainda não foram implementados.

Os prazos de SLA, os tempos de preparo e a cota de atendimento são parâmetros didáticos da simulação. Eles não representam medições de restaurantes nem padrões oficiais do setor.

## Documentação

- [Escopo e regras de negócio](docs/escopo.md)
- [Modelagem e diagrama inicial](docs/modelagem.md)
- [Dicionário de classes e métodos](docs/dicionario.md)
- [Planejamento das sete etapas](docs/planejamento.md)
- [Relatório parcial da primeira entrega](entregas/primeira_entrega/relatorio_parte_1_contexto.docx)
- [Apresentação revisada da primeira entrega](entregas/primeira_entrega/apresentacao_contexto_10-11_revisada.pptx)

## Estrutura inicial

```text
docs/                 Escopo, modelagem, dicionário e planejamento
entregas/             Materiais das entregas acadêmicas
src/fastfood/domain/  Tipos, regras e eventos compartilhados
```

O núcleo da Etapa 1 usa apenas a biblioteca padrão do Python. As dependências de interface serão definidas quando o Streamlit for integrado.

## Fluxo colaborativo

As etapas seguem a sequência descrita em [docs/planejamento.md](docs/planejamento.md). O responsável deve explicar sua contribuição, registrar commits próprios e entregar os contratos para revisão antes do início da etapa seguinte.
