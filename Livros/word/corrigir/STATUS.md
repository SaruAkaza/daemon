# Status de Livros Aguardando Correção

## Guia de Itens Mágicos

**Data de remoção:** 2026-06-05
**Motivo:** OCR severamente degradado — inviável catalogar sem retrabalho garantido.
**Status:** Aguardando fonte de melhor qualidade / re-OCR.

### Diagnóstico (Volume 1, pg 18–146)
| Métrica | Valor | Observação |
|---|---|---|
| Acentos preservados | ~1.0% das palavras | Em pt normal seria ~25–30% |
| Palavras irreconhecíveis (dic pt) | 39% das únicas | OCR residual, não só acentos |
| Exemplos | `abenoado`=abençoado, `aceleraao`=aceleração, `acerlar`=acertar | Reconstrução exigiria revisão linguística pesada |

### O que já foi feito (reaproveitável quando houver OCR melhor)
- **Estrutura mapeada** (`scripts/analyze_itens_magicos.py`): paginação 1–288 contínua;
  corpo dos itens pg 18–271 (A→Z); **Vol 1 = pg 18–146 (A–H)**, Vol 2 = pg 147–271 (I–Z);
  apêndices/sumário/OGL identificados para descarte.
- **`scripts/requiem_clean.py::fix_ocr()`** (opt-in, aditivo): repara ç-variantes
  (`<;` `c;` `c:;:`), `0`→o isolado (preserva tabelas), `urn`→um, `s6`→só, `dane`→dano,
  `enta~`→então, `ld/Id+díg`→1d. NÃO resolve a acentuação perdida em massa.
- Decisões de escopo registradas em `coordination/books/guia-de-itens-magicos.md`:
  piloto por volume, tabelas 1d100 estruturadas, lista única alfabética.

### Próximo passo
Re-OCR do PDF original (ou fonte melhor). Com OCR decente, a estrutura e o `fix_ocr()`
já permitem retomar direto pela catalogação do Vol 1.

---

## Anjos - A Cidade de Prata

**Data de remoção:** 2026-06-05  
**Motivo:** Qualidade de texto insuficiente - 232+ erros OCR não corrigidos  
**Status:** Aguardando revisão manual

### Erros Identificados

| Tipo | Quantidade | Exemplo | Solução |
|------|-----------|---------|---------|
| Ambiguidade rn→m | 195 | "Internet" vs "Intemet" | Análise de contexto |
| Acentuação | 32+ | "política" vs "politica" | Revisão semântica |
| OCR complexo | 5+ | Títulos corrompidos | Revisão manual |

### Tentativas Anteriores

1. **OCR Cleanup Pipeline** (5 fases)
   - Decomposição de ligaduras
   - Junção de fragmentos
   - Correção de padrões numéricos
   - Remoção de Unicode inválido
   - Filtro de títulos corrompidos
   - **Resultado:** Removeu 641 linhas de ruído puro, mas erros contextuais permaneceram

2. **Agressiva Text Cleanup**
   - Removeu linhas de puro OCR noise
   - Limpou caracteres corrompidos
   - **Resultado:** 5953 linhas finais, mas qualidade ainda insuficiente

3. **Estruturação JSON**
   - Consolidou Regras Base + Usos de Pontos de Fé
   - Reconstruiu 24 aprimoramentos do zero
   - Reordenou blocos (Custo antes de Descrição)
   - **Resultado:** Estrutura correta, mas texto com ruído

### Próximos Passos

**Opção 1: Revisão Manual (Recomendado)**
- Passar arquivo de texto LIMPO (base sólida) para revisão
- Revisor humano aplica análise semântica aos 232 erros
- Mais rápido e confiável que scripts ambíguos

**Opção 2: Scripts Contextuais**
- Criar regras muito específicas por contexto
- Maior risco de introduzir novos erros
- Não recomendado

**Opção 3: Híbrido**
- Scripts para fixes unambíguos
- Humano aprova/rejeita cada correção
- Balanço entre automação e qualidade

### Scripts Reutilizáveis

Os seguintes scripts podem ser usados em outros livros:

```bash
# Remove OCR noise lines (page numbers, symbols, etc.)
python scripts/aggressive_text_cleanup.py

# Applys safe, unambiguous fixes only
python scripts/final_text_cleanup.py

# Normalizes structure (Regras Base consolidation)
python scripts/consolidate_anjos_regras_base.py

# Rebuilds content from clean source
python scripts/fix_anjos_aprimoramentos_rebuild.py
```

### Arquivo Original

- **Localização:** Livros/word/corrigir/Anjos_A_Cidade_de_Prata.docx
- **Tamanho:** 156 KB
- **Linhas de texto:** 5,953 (após limpeza)
- **Estrutura:** JSON estruturado (removido da aplicação até conclusão)
