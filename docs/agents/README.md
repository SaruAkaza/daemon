# Contratos de Papéis de Agentes (Role Contracts)

Este diretório contém os contratos formais que definem a identidade, autoridade, escopo, regras e interfaces de cada papel especializado na arquitetura multiagente do **Daemon Tools**.

---

## 1. Por que Existem Contratos de Papéis?

O processamento do acervo de livros do Daemon/Trevas envolve múltiplas fases de complexidade: desde a auditoria de direitos e correção de OCR bruto até a normalização semântica de entidades, relações de regras e montagem do catálogo pesquisável.

Os contratos existem para:
- **Evitar sobreposição e conflito**: Delimitar com precisão o que cada papel pode e não pode fazer.
- **Garantir previsibilidade**: Estabelecer contratos rígidos de entrada (*Input Contract*) e saída (*Output Contract*) para alimentar o futuro *Context Pack Builder*.
- **Assegurar fidelidade e proveniência**: Impedir que erros em uma camada sejam disfarçados silenciosamente em outra.
- **Facilitar orquestração e testes**: Permitir que gates determinísticos avaliem se o trabalho de um estágio está completo e aderente aos padrões.

---

## 2. Papel Lógico vs. Executor Físico (Modelo)

> [!IMPORTANT]
> `source-agent`, `extraction-agent`, `editorial-agent`, `entity-agent`, `relations-agent`, `frontend-agent`, `qa-release-agent` e `orchestrator` são **papéis lógicos** do Daemon Tools. Eles não representam obrigatoriamente processos, modelos, threads ou sessões independentes.

- **Papel Lógico**: Define uma função no ciclo de vida de dados (ex.: extração, normalização, relações).
- **Executor Físico**: O modelo de linguagem, subagente, processo ou humano que assume a persona e as restrições daquele papel em um determinado momento.

Nesta fase do projeto, o ambiente principal de desenvolvimento é o **Antigravity** com o modelo **Gemini 3.7 High** atuando como executor primário. O mesmo executor pode desempenhar sucessivamente o papel de *Extraction Agent*, *Editorial Agent* ou *Entity Agent*, adotando em cada etapa o contexto mínimo suficiente e o contrato correspondente. No futuro, a arquitetura suportará paralelismo e subagentes autônomos sem qualquer necessidade de refatoração nos contratos.

---

## 3. Neutralidade de Provedor (Provider-Neutrality)

Nenhum contrato depende permanentemente de uma API, prompt syntax proprietária ou recurso exclusivo de Gemini, Antigravity, Claude, ChatGPT ou qualquer outro provedor. 

A arquitetura define:
- **Prompt define identidade.**
- **Contexto define o mundo.**
- **Contrato define autoridade e entregáveis.**

---

## 4. Estrutura Padrão de um Contrato

Todos os contratos neste diretório seguem rigorosamente a mesma estrutura de 16 seções:

1. `## Identity` — Nome formal e papel do agente.
2. `## Mission` — Objetivo fundamental da função.
3. `## Question This Role Answers` — A pergunta norteadora do papel.
4. `## Mandatory Context` — Documentos e dados indispensáveis para execução.
5. `## Optional Context` — Informações complementares opcionais.
6. `## Input Contract` — Formato e requisitos dos dados de entrada.
7. `## Output Contract` — Formato e garantias dos dados produzidos.
8. `## Primary Write Scope` — Diretórios e arquivos autorizados para escrita.
9. `## Read-Only Scope` — Diretórios e dados que o agente pode ler mas não alterar.
10. `## Forbidden Actions` — Ações estritamente proibidas para o papel.
11. `## Entry Gate` — Condições mínimas para iniciar o trabalho.
12. `## Exit Gate` — Condições obrigatórias para considerar a etapa concluída.
13. `## Human Escalation` — Gatilhos que exigem intervenção humana imediata.
14. `## Failure Routing` — Roteamento de erros para a camada correta do pipeline.
15. `## Examples` — Cenários práticos de aplicação do papel.
16. `## Base Prompt` — Prompt base compacto para inicialização do papel.

---

## 5. Relação com `AGENTS.md` e a Hierarquia Canônica

`AGENTS.md` na raiz do repositório é o ponto de entrada global. Os contratos em `docs/agents/` detalham as especializações. Ambos estão subordinados à Constituição (`docs/architecture/constitution.md`) e às regras editoriais de `docs/reference/cataloging-rules.md`.
