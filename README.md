# Sistema de filas de prioridade para fast food

Projeto académico de Algoritmos e Programação Orientada a Objetos. O nosso objetivo é construir uma simulação de fila para pedidos de fast food, com prioridade, proteção contra starvation, acompanhamento de SLA, auditoria SQL e interface Streamlit.

## Estado atual

O repositório acaba de concluir a **Etapa 3 — Estrutura da fila**. Até ao momento, foram implementados:
- **Etapa 1:** Escopo, enums, regras de negócio configuráveis e contratos de domínio.
- **Etapa 2:** Estruturação de pedidos (`Order`) e do ciclo de vida dos tickets (`Ticket`).
- **Etapa 3:** Filas independentes em memória (`collections.deque`) garantindo ordem FIFO por nível de prioridade.

A política contra starvation (Etapa 4), o motor de simulação completo (Etapa 5), a auditoria SQL (Etapa 6) e a aplicação Streamlit (Etapa 7) estão mapeados para as próximas entregas.

*Nota: Os prazos de SLA, tempos de preparo e a cota de atendimento são parâmetros didáticos da simulação. Eles não representam medições de restaurantes reais.*

## Documentação

- [Escopo e regras de negócio](docs/escopo.md)
- [Modelagem e diagrama inicial](docs/modelagem.md)
- [Dicionário de classes e métodos](docs/dicionario.md)
- [Planeamento das sete etapas](docs/planejamento.md)
- [Relatório parcial da primeira entrega](entregas/primeira_entrega/relatorio_parte_1_contexto.docx)
- [Apresentação revisada da primeira entrega](entregas/primeira_entrega/apresentacao_contexto_10-11_revisada.pptx)

## Estrutura do projeto

```text
docs/                 Escopo, modelagem, dicionário e planeamento
entregas/             Materiais das entregas académicas
src/fastfood/
  domain/             Tipos, regras, eventos, pedidos e tickets
  queues/             Estrutura de dados das filas (PriorityQueue)
tests/                Suíte de testes automatizados do projeto
```

O núcleo desenvolvido até agora utiliza estritamente a biblioteca padrão do Python. As bibliotecas de terceiros serão especificadas quando a interface visual for integrada.

## Instalação e Testes Automatizados

1. **Instale o pacote localmente em modo editável** (vincula automaticamente a pasta `src/` ao ambiente sem precisar definir a variável `PYTHONPATH` manualmente):

   ```bash
   uv pip install -e .
   ```

2. **Execute a suíte de testes automatizados:**

   ```bash
   uv run python -m unittest discover -s tests -p "test*.py" -v
   ```

3. **Rode o linter (Ruff) para checagem do código:**

   ```bash
   uv run ruff check --fix
   ```

## Fluxo colaborativo

O desenvolvimento segue a divisão descrita em [docs/planejamento.md](docs/planejamento.md). Cada integrante é responsável pelo código, documentação e testes da sua respetiva etapa. O fluxo determina que a etapa seguinte só pode ser iniciada após o integrante atual ter a sua Pull Request revista e integrada na branch `main`.