# Pipeline e Ciclo de Vida de Dados

Este documento define o pipeline oficial de transformação de dados e a máquina de estados para processamento do acervo no Daemon Tools.

---

## 1. Fluxo de Estágios do Pipeline

O pipeline opera como uma cadeia sequencial de estágios especializados:

```text
SOURCE
  ↓
EXTRACTION
  ↓
EDITORIAL
  ↓
ENTITIES
  ↓
RELATIONS
  ↓
FRONTEND
  ↓
QA
  ↓
RELEASE
```

---

## 2. Responsabilidades por Estágio

| Estágio | Responsabilidade Principal | Artefatos / Saídas |
| :--- | :--- | :--- |
| **`SOURCE`** | Identificação da fonte original, inventário, cálculo de hash e checagem preliminar de direitos autorais. | `Livros/`, `data/index/sources.json` |
| **`EXTRACTION`** | Extração do texto bruto, correção de OCR, resolução de mojibake, ligaduras e hifenização. | `data/text/<livro>.txt` |
| **`EDITORIAL`** | Segmentação textual por página/seção, classificação de blocos e garantia de cobertura total. | `data/books/<livro>.json` |
| **`ENTITIES`** | Normalização de entidades individuais em esquemas canônicos estruturados com proveniência. | `data/entities/<categoria>.json` |
| **`RELATIONS`** | Mapeamento de vínculos, referências cruzadas, pré-requisitos e regras associadas. | Entidades enriquecidas, grafos de regras |
| **`FRONTEND`** | Montagem de áreas de navegação, índices de busca e sincronização dos assets estáticos. | `data/areas/*.json`, `docs/assets/data/` |
| **`QA`** | Validação automatizada determinística (schemas, integridade, cobertura, sintaxe) e checagens visuais. | Relatórios de QA, execução de testes |
| **`RELEASE`** | Autorização final e publicação para a base pública do GitHub Pages. | Deploy em produção (`docs/`) |

---

## 3. Estados de Stage e Estados de Job

### Estados de Stage (Execução Técnica)

- `waiting`: Aguardando conclusão de dependências de estágios anteriores.
- `ready`: Pré-requisitos cumpridos; pronto para execução.
- `running`: Estágio em processamento ativo.
- `pass`: Execução concluída com sucesso e verificada pelos gates.
- `fail`: Falha técnica ou erro determinístico na validação.
- `blocked`: Impedimento externo ou dependência não atendida.
- `human_review`: Requer intervenção humana para resolução.

### Estados de Job (Ciclo de Vida da Tarefa)

- `todo`: Planejado mas ainda não iniciado.
- `in_progress`: Em desenvolvimento ativo pelo agente ou executor.
- `blocked`: Bloqueado por ambiguidade, direitos ou dependência externa.
- `needs_review`: Pronto para auditoria e validação.
- `approved`: Validado tecnicamente e aprovado pelos revisores.
- `done`: Concluído definitivamente após validação humana registrada.

---

## 4. Regra de Não-Correção Silenciosa no QA

> [!IMPORTANT]
> **QA não corrige silenciosamente erro semântico. O erro retorna ao estágio onde nasceu.**

Se durante o estágio de `QA` (ou `FRONTEND`) for identificada uma falha estrutural ou semântica, o fluxo não deve aplicar "gambiarras" na camada de visualização. O defeito deve ser roteado para o estágio de origem:

```text
Erro de OCR / Caracteres corrompidos  ──→  EXTRACTION
Erro de corte de página / Bloco mal segmentado  ──→  EDITORIAL
Custo ou atributo incorreto na entidade  ──→  ENTITIES
Vínculo quebrado entre magia e caminho  ──→  RELATIONS
Falha de renderização ou layout  ──→  FRONTEND
Incerteza legal ou de direitos autorais  ──→  HUMAN REVIEW
```
