# ADR-0002 — Human Validation Required For Done

## Status
Accepted

## Context
Em pipelines automatizados de processamento de linguagem natural e extração de regras de RPG, a aprovação técnica em gates determinísticos (como validação de JSON Schema, ausência de erros de sintaxe ou cobertura de páginas) é uma condição necessária, mas não suficiente, para garantir a fidelidade semântica e a qualidade editorial da experiência do usuário.

A ausência de erros em testes automatizados (`PASS` técnico) não garante que nuances de regras, interpretações sutis de termos ou decisões de layout correspondam perfeitamente à intenção original do livro e ao padrão do produto.

## Decision
Fica estabelecido que **nenhum job, lote ou livro pode transicionar para o estado final `done` sem que haja uma validação humana explícita, registrada e resolvida**.

Agentes e automações podem avançar um job através dos estados `todo`, `in_progress`, `blocked`, `needs_review` e `approved` (em nível de QA técnico), mas o encerramento em `done` é prerrogativa exclusiva da supervisão humana.

## Consequences
### Positivas
- **Fidelidade Editorial Garantida**: O usuário mantém autoridade final sobre o acervo e decisões ambíguas.
- **Proteção Contra Erros Silenciosos**: Impede que alucinações sutis ou desvios de regra passem despercebidos para a versão pública de produção.
- **Transparência**: Toda conclusão de trabalho possui uma assinatura de auditoria humana documentada.

### Negativas / Custos
- A velocidade de entrega final depende da disponibilidade do revisor humano para inspecionar os artefatos em `needs_review`/`approved`.
- Jobs permanecem aguardando validação antes do arquivamento definitivo.

## Supersedes
None
