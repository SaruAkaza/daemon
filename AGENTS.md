# Daemon Tools — Agent Entry Point

Este repositório transforma livros do universo Daemon/Trevas em uma referência digital rastreável, validada e pesquisável, inspirada no modelo 5e.tools.

## Leitura Obrigatória

1. `docs/architecture/constitution.md`
2. `docs/architecture/project-context.md`
3. `docs/architecture/pipeline.md`
4. `docs/reference/cataloging-rules.md`
5. `docs/reference/data-model.md`
6. `coordination/README.md`
7. Contrato específico do agente, quando existir
8. Contrato do livro atual (`coordination/books/<livro>.md` ou book context)
9. Job atual
10. Handoff anterior, quando existir

## Regras Centrais

- **Limpeza Textual Prévia**: Limpe e certifique o texto bruto antes de qualquer categorização semântica.
- **Proveniência**: Preserve fonte e página em todos os dados derivados.
- **Não Invenção**: Nunca invente regras ausentes, custos não declarados ou informações omitidas no material original.
- **Cobertura Total**: Toda página processada precisa ter cobertura e destino classificado.
- **Validação Determinística**: Use scripts e testes determinísticos para validações técnicas.
- **Registro de Incerteza**: Registre ambiguidades e dúvidas como pendências em vez de fabricar conclusões.
- **Direitos Autorais**: Conteúdo protegido ou com direitos desconhecidos não é publicado publicamente de forma automática.
- **Critério de Done**: `done` exige validação humana registrada e resolvida.

## Memória Durável

O repositório Git é a memória durável do sistema.

Não assuma que outro agente ou execução subsequente compartilha histórico de conversa ou contexto em memória.

## Coordenação

Novos trabalhos agentic usarão jobs e handoffs estruturados quando essa camada for implementada.

A coordenação operacional legada (Codex/Claude em `coordination/`) continua válida durante o processo de transição.

## Validação

Siga os comandos, suítes de testes e gates definidos em `docs/architecture/pipeline.md`.
