# Sistema de Contexto e Hierarquia de Informação

Este documento estabelece o modelo de montagem de contexto para agentes no Daemon Tools, garantindo clareza, economia de tokens e precisão na execução.

---

## 1. Camadas de Contexto

O contexto fornecido a qualquer agente é montado em camadas progressivas e modulares:

```text
Constitution
    +
Project Context
    +
Domain Context
    +
Book Context
    +
Job Context
    +
Handoff Context
    +
Task Context
    +
Output Contract
```

### Detalhamento das Camadas

1. **Constitution** (`docs/architecture/constitution.md`): As regras invioláveis, invariantes de autoridade e princípios de fidelidade.
2. **Project Context** (`docs/architecture/project-context.md`): Visão técnica geral da stack, estrutura de arquivos e comandos de validação.
3. **Domain Context** (`docs/reference/cataloging-rules.md`, `docs/reference/data-model.md`): Regras editoriais canônicas e taxonomia do sistema Daemon.
4. **Book Context** (`coordination/books/<livro>.md` ou metadados da obra): Particularidades, convenções e exceções do livro em processamento.
5. **Job Context**: A definição do lote de trabalho ativo e o escopo esperado.
6. **Handoff Context** (`coordination/handoff/` ou notas do agente anterior): O histórico imediato do que foi feito e quais pontos requerem atenção.
7. **Task Context**: A instrução operacional precisa da tarefa em execução no momento.
8. **Output Contract**: O formato exato (schema JSON, markdown estruturado, diff de arquivo) que o agente deve produzir.

---

## 2. Princípio do Contexto Mínimo Suficiente (Minimum Sufficient Context)

> [!TIP]
> **Minimum Sufficient Context**: Um agente deve receber exclusivamente o contexto necessário e suficiente para cumprir sua responsabilidade imediata com máxima acurácia.

Poluir o contexto do agente com dados operacionais não relacionados degrada a precisão, aumenta a latência e desperdiça tokens:

- **Agente de Frontend** não precisa carregar o texto bruto do livro inteiro de 200 páginas.
- **Agente de Extração (Extraction)** não precisa carregar as regras de interface web ou de deploy no GitHub Pages.
- **Agente de Entidades (Entity)** não deve receber detalhes de CI/CD ou histórico irrelevante de versões.
- **Exceção de Rastreabilidade**: Nunca omita identificadores de fonte (`source`) e numeração de página (`page`), pois a proveniência é invariante.
