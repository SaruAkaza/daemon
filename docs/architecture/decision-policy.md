# Política de Decisão e Gestão de Incerteza

Este documento estabelece as diretrizes para tomada de decisão autônoma por agentes, níveis de confiança aceitáveis e protocolos de escalonamento para validação humana.

---

## 1. Princípio de Autoridade Decisória

Toda e qualquer decisão técnica ou semântica deve respeitar estritamente a hierarquia de autoridade definida na Constituição (`docs/architecture/constitution.md`):

1. Documento fonte original (`Livros/`)
2. Decisão humana aprovada e registrada
3. Regras editoriais canônicas (`docs/reference/cataloging-rules.md`)
4. Schemas e contratos globais (`schemas/`)
5. Documentação de arquitetura (`docs/architecture/`)
6. Contrato específico do livro
7. Dados já certificados
8. Precedentes aprovados
9. Handoff atual
10. Inferência do agente

---

## 2. Níveis de Confiança (Confidence Scoring)

Para classificação, extração e normalização de dados ambíguos, os agentes devem avaliar internamente o grau de certeza. Os limites padrão são:

| Nível de Confiança | Score Conceitual | Protocolo de Ação |
| :--- | :--- | :--- |
| **Alta Confiança** | `>= 0.90` | O agente pode avançar e consolidar a operação, desde que os gates determinísticos e testes passem. |
| **Média Confiança** | `0.70 – 0.89` | A operação pode prosseguir com registro de alerta (*warning*), ficando sinalizada para revisão no estágio de QA. |
| **Baixa Confiança** | `< 0.70` | O agente **não pode** certificar ou inventar a resolução; a dúvida deve ser registrada formalmente como pendência para revisão humana. |

> [!NOTE]
> Estes valores percentuais representam *defaults* arquiteturais conceituais e poderão ser calibrados conforme o sistema evoluir.

---

## 3. Precedentes vs. Regras Universais

- Precedentes de categorizações anteriores servem como guia de consistência, mas **não substituem** as regras universais e os schemas formais.
- Se um precedente histórico violar uma regra canônica explícita, a regra canônica prevalece e o precedente deve ser marcado para saneamento.

---

## 4. O Papel da Decisão Humana

- Uma decisão humana aprovada e registrada em contrato de livro, relatório ou issue encerra a ambiguidade para aquele caso específico e pode estabelecer um novo precedente documentado.
- Agentes nunca devem anular ou reinterpretar uma decisão humana explícita sem solicitação direta.
