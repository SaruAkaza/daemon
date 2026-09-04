# Constituição do Sistema Multiagente Daemon Tools

Este documento define os princípios invioláveis e as regras fundamentais de autoridade, fidelidade e governança para todos os agentes (humanos ou artificiais) que operam no repositório Daemon Tools. Nenhum agente, modelo ou automação possui permissão para ignorar ou violar estas diretrizes.

---

## 1. Hierarquia de Autoridade

Quando houver divergência entre fontes de informação, a precedência deve obedecer rigorosamente à seguinte ordem:

1. **Documento Fonte Original** (`Livros/`)
2. **Decisão Humana Aprovada e Registrada**
3. **Regras Editoriais Canônicas** (`docs/reference/cataloging-rules.md`)
4. **Schemas e Contratos Globais** (`schemas/`)
5. **Documentação de Arquitetura** (`docs/architecture/`)
6. **Contrato Específico do Livro** (`coordination/books/` ou book context)
7. **Dados Já Certificados** (`data/entities/`, `data/areas/`)
8. **Precedentes Aprovados e Registrados**
9. **Handoff Atual** (`coordination/handoff/` ou handoffs de jobs)
10. **Inferência do Agente**

> [!IMPORTANT]
> **Regra de Não-Sobrescrita Silenciosa**: Uma camada inferior na hierarquia NUNCA pode sobrescrever silenciosamente uma camada superior. Se um agente identificar inconsistência ou erro em camada superior, deve registrar a divergência como pendência para revisão humana.

---

## 2. Preservação de Fontes

- A pasta `Livros/` contém os arquivos fonte originais (PDFs, DOCXs).
- Nenhuma automação, script ou agente tem autorização para apagar, alterar ou destruir silenciosamente o material original contido em `Livros/`.
- O processamento é estritamente derivativo e não destrutivo.

---

## 3. Proveniência e Rastreabilidade

- Todos os dados derivados (textos extraídos, segmentos, entidades, blocos e relações) devem manter vínculo explícito com o identificador da fonte (`source`) e o número da página original (`page`).
- Nenhuma entidade pode ser gerada ou publicada como fato sem a devida ancoragem de proveniência.

---

## 4. Não-Invenção e Fidelidade Textual

- Modelos de linguagem e agentes NÃO podem preencher lacunas, supor custos, inventar regras ausentes ou deduzir valores mecânicos apenas porque algo "parece provável" ou "faz sentido no sistema".
- Se um atributo, custo, pré-requisito ou efeito não estiver explícito no texto fonte, ele não deve ser fabricado.

---

## 5. Separação Semântica Estrita

O ciclo de transformação de dados opera em camadas conceituais estritamente separadas:

- **Fonte**: O arquivo original imutável (`Livros/`).
- **Extração**: O texto bruto recuperado (`data/text/`).
- **Segmento**: A divisão estrutural e textual por página e seção (`data/books/`).
- **Entidade**: O objeto canônico normalizado (`data/entities/`).
- **Relação**: Os vínculos entre entidades, categorias e regras.
- **Apresentação**: A exibição e navegação para o usuário final (`data/areas/`, `docs/assets/data/`).

Problemas de uma camada devem ser resolvidos na camada de origem (ex.: erro de OCR é resolvido na Extração/Limpeza, não disfarçado na Apresentação).

---

## 6. Cobertura Total de Páginas

- Toda e qualquer página processada de um livro precisa ter classificação e destino explícito.
- Nenhuma página pode ser descartada silenciosamente. Capas, sumários, créditos, tabelas, fichas e páginas em branco devem ser mapeadas em `data/books/<livro>.json`.

---

## 7. Tratamento de Incerteza e Ambiguidade

- Diante de ruído de OCR, layout truncado, termos ambíguos ou inconsistências de regras no texto original: **registre a dúvida formalmente**.
- É proibido adivinhar, aproximar ou marcar como concluído sem certeza comprovável.

---

## 8. Direitos Autorais e Publicação Segura

- Materiais protegidos por direitos autorais estritos ou com status de licenciamento desconhecido não podem ser publicados em texto integral no repositório público ou no GitHub Pages.
- A distribuição pública deve focar em metadados, índices estruturados, referências de página e resumos descritivos autorizados.

---

## 9. Governança e Decisão Humana

As seguintes ações exigem obrigatoriamente validação humana registrada:

- Alterações em schemas globais (`schemas/`);
- Resolução de conflitos semânticos relevantes ou contradições graves entre fontes;
- Liberação pública de dados de obras com direitos restritos;
- Modificações destrutivas ou refatorações de grande escala na base de dados.

---

## 10. Critério Universal de Conclusão (Done)

> [!CAUTION]
> **Um job NÃO PODE entrar em `done` sem que exista validação humana final registrada e resolvida.**
