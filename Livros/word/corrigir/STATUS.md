# Status de Livros Aguardando Correção

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
