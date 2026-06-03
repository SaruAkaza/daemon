# DOCX Structured Pipeline — Design Spec

**Data:** 2026-06-03
**Escopo:** Fase 1 — DOCX only. PDF é segunda fase.
**Motivação:** Catalogação anterior usou heurística sobre texto sujo. Lote marcado `invalid_experimental`. Pipeline novo exige texto limpo e estrutura antes de qualquer classificação.

---

## Pipeline alvo

```
DOCX  →  data/structured/<slug>.json  →  data/blocks/<slug>.json
                                               ↓ (fase futura)
                                         classify_blocks.py
                                               ↓
                                         build_catalog_from_blocks.py
```

Novos livros entram por esse caminho. Livros já no pipeline antigo (`data/segments/`) não são migrados automaticamente — migram quando revisados manualmente. `data/segments/` fica como legado.

---

## Modelo de dados

### `data/structured/<slug>.json`

Árvore hierárquica do documento, limpa.

```json
{
  "version": 1,
  "source": "abismo-infinito-quick-start",
  "sourceType": "docx",
  "file": "Abismo-Infinito-Quick-Start.docx",
  "title": "Abismo Infinito - Quick Start",
  "extractedAt": "2026-06-03T12:00:00",
  "warnings": [
    "no_chapter_detected: documento sem Heading 1 real; estrutura inferida por heurística"
  ],
  "children": [
    {
      "type": "frontmatter",
      "children": [
        { "type": "paragraph", "text": "...", "page": 1 }
      ]
    },
    {
      "type": "chapter",
      "heading": "Capítulo 2: Personagens",
      "level": 1,
      "page": 5,
      "children": [
        {
          "type": "section",
          "heading": "Exobiólogo",
          "level": 2,
          "page": 7,
          "children": [
            { "type": "paragraph", "text": "...", "page": 7 },
            {
              "type": "table",
              "headers": ["Perícia", "Nível"],
              "rows": [["Biologia", "2"]],
              "page": 8
            }
          ]
        }
      ]
    },
    {
      "type": "index",
      "heading": "Índice",
      "page": 120,
      "children": []
    }
  ]
}
```

**Tipos de nó válidos:** `frontmatter`, `chapter`, `section`, `subsection`, `paragraph`, `table`, `special_block`, `index`.

**`page`:** número de página DOCX estimado por contagem de page breaks no XML. `null` quando não identificável.

**`sourceType`:** `"docx"` agora. Campo reservado para `"pdf"` na fase 2.

---

### `data/blocks/<slug>.json`

Lista plana derivada da árvore — formato de trabalho para catalogação e revisão.

```json
{
  "version": 1,
  "source": "abismo-infinito-quick-start",
  "sourceType": "docx",
  "blocks": [
    {
      "id": "abismo-infinito-quick-start--0042",
      "type": "paragraph",
      "path": ["Capítulo 2: Personagens", "Exobiólogo"],
      "areaHint": null,
      "text": "O exobiólogo é o cientista especializado em...",
      "source": {
        "book": "Abismo Infinito - Quick Start",
        "file": "Abismo-Infinito-Quick-Start.docx",
        "page": 7
      }
    }
  ]
}
```

**`id`:** `{slug}--{sequência zero-padded com 4 dígitos}`.
**`path`:** breadcrumb de headings ancestrais. Permite classificar sem reabrir a árvore.
**`areaHint`:** começa `null`. Preenchido pelo futuro `classify_blocks.py`.
**Blocos `frontmatter` e `index`:** incluídos com seus tipos, ignorados na catalogação final por tipo.

---

## Scripts

### `scripts/build_docx_structured.py`

**Responsabilidade única:** DOCX → `data/structured/<slug>.json`

**Execução:**
```bash
python scripts/build_docx_structured.py --source abismo-infinito-quick-start
python scripts/build_docx_structured.py --all          # pula já processados
python scripts/build_docx_structured.py --all --force  # reprocessa todos
```

**Algoritmo (passagem única):**

1. Abrir DOCX com `python-docx`
2. Pré-varredura para detecção de padrões repetidos (ver limpeza abaixo)
3. Caminhar elementos em ordem (parágrafos + tabelas)
4. Para cada elemento: limpar → classificar → inserir na árvore
5. Classificar frontmatter e index (ver regras abaixo)
6. Escrever JSON + atualizar `data/index/structured-status.json`

**Detecção de heading (prioridade decrescente):**
1. Estilo Word `Heading 1/2/3` → level 1/2/3
2. Heurística: linha curta (<80 chars) + negrito + sem ponto final → level por tamanho de fonte relativo ou posição
3. Padrão textual: `"Capítulo N"`, `"PARTE"`, `"Apêndice"` no início

---

### `scripts/build_docx_blocks.py`

**Responsabilidade única:** `data/structured/<slug>.json` → `data/blocks/<slug>.json`

**Execução:**
```bash
python scripts/build_docx_blocks.py --source abismo-infinito-quick-start
python scripts/build_docx_blocks.py --all
```

**Algoritmo:** caminhada DFS na árvore acumulando path de headings. Para cada nó leaf (`paragraph`, `table`, `special_block`) emite um block com o path atual. Nós `frontmatter` e `index` também emitem blocks com seus tipos preservados.

Sem lógica de limpeza — responsabilidade do script anterior.

---

## Regras de limpeza (aplicadas em `build_docx_structured.py`)

### Passo 1 — Detecção de padrões repetidos (pré-parse, uma vez por documento)

Varre todos os parágrafos curtos (<120 chars). Conta frequência por texto normalizado por grupo de página (estimado por page breaks no XML DOCX). Qualquer string que aparece em ≥ 40% dos grupos de página entra na lista negra `repeated_patterns`.

Exemplos: `"Daemon Trevas — Sistema de RPG"`, `"© Editora Daemon"`, número de página solto (`"3"`).

### Passo 2 — Filtros por parágrafo (em ordem)

```
1. texto em repeated_patterns?        → descartar parágrafo
2. só número ou só símbolo?           → descartar (número de página solto)
3. encoding repair                    → reutilizar lógica de repair_encoding.py
                                         (Shift-29, mojibake, latin1 mal decodificado)
4. hifenização quebrada               → juntar "pala-\nbra" → "palavra"
                                         apenas quando: hífen é último char da linha
                                         E próxima linha começa com minúscula
5. espaços múltiplos                  → colapsar para um espaço
6. \r, \t, \x00 e outros de controle → remover
7. aspas tipográficas                 → normalizar para " e '
```

### Passo 3 — Classificação de index/sumário

Nó é `type: "index"` se:
- Heading contém `índice`, `sumário`, `conteúdo`, `table of contents` (case-insensitive), **ou**
- ≥ 60% das linhas do bloco seguem padrão `texto .... N` (pontinhos + número)

### Passo 4 — Frontmatter

Todo conteúdo antes do primeiro `chapter` (Heading 1) é agrupado em único nó `frontmatter`.

Se o documento não tiver nenhum `chapter`, **toda a árvore** fica sob `frontmatter` e o warning `no_chapter_detected` é emitido. Para catalogação desses livros, será necessário promover headings por heurística em etapa futura separada.

### O que não é tratado aqui

- URLs no meio de frase (`www...`) — não viram heading; tratamento conservador pode ser adicionado depois
- Tabelas mal formatadas como texto corrido — problema de PDF/OCR, fora do escopo DOCX
- Classificação de área (`areaHint`) — responsabilidade do futuro `classify_blocks.py`

---

## Tratamento de erros

### Warnings no JSON de saída

```json
"warnings": [
  "no_chapter_detected: documento sem Heading 1 real; estrutura inferida por heurística",
  "encoding_repair_applied: 3 parágrafos tiveram encoding reparado",
  "repeated_pattern_threshold_low: apenas 12% de repetição detectada, padrão ignorado"
]
```

### Falhas fatais vs. warnings

| Situação | Comportamento |
|---|---|
| DOCX corrompido (não abre) | Fatal — registra `status: "failed"` no status index, pula |
| DOCX com 0 parágrafos | Warning + structured e blocks vazios |
| Sem Heading 1 real | Warning `no_chapter_detected`, árvore toda sob frontmatter |
| Encoding irrecuperável num parágrafo | Warning, parágrafo substituído por `[parágrafo ilegível]` |
| Tabela sem cabeçalho identificável | Incluída com `headers: null` |

### `data/index/structured-status.json`

```json
{
  "abismo-infinito-quick-start": {
    "status": "ok",
    "warnings": ["no_chapter_detected"],
    "structuredAt": "2026-06-03T12:00:00",
    "blocksAt": "2026-06-03T12:00:01",
    "blockCount": 87,
    "file": "Abismo-Infinito-Quick-Start.docx"
  },
  "arkanun": {
    "status": "failed",
    "error": "docx_corrupt",
    "structuredAt": null,
    "blocksAt": null
  }
}
```

`--all` pula livros com `status: "ok"` e `structuredAt` mais recente que o DOCX de origem. Reprocessa com `--force`.

---

## Relação com pipeline existente

| Script | Status |
|---|---|
| `extract_text.py` | Mantido como utilitário auxiliar/debug |
| `repair_encoding.py` | Mantido; lógica reutilizada internamente |
| `segment_docx_text.py` | Legado — não usado para livros novos |
| `build_docx_segment_catalog.py` | Aposentado para catalogação final |
| `build_docx_structured.py` | **Novo** |
| `build_docx_blocks.py` | **Novo** |
| `classify_blocks.py` | Futuro (fase 2) |
| `build_catalog_from_blocks.py` | Futuro (fase 3) |

Livros já em `data/segments/` não são migrados automaticamente. Migram quando revisados um a um.

---

## Fora do escopo desta fase

- PDF: segunda fase. Campos `sourceType`, `page` e `source` já preparados para receber.
- `classify_blocks.py`: preenchimento de `areaHint` nos blocks
- Interface de revisão: leitura de `data/blocks/` pelo frontend
- Extração de entidades a partir de blocks classificados
