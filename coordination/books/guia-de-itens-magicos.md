# Contrato — Guia de Itens Mágicos

- **Agente:** Claude (worktree `daemon-claude`, branch `claude-pilots`)
- **DOCX:** `Livros/word/Guia_de_Itens_Magicos_OCR_alta_qualidade.docx`
- **source / pilot:** `guia-de-itens-magicos`
- **Reivindicado:** 2026-06-05
- **NÃO confundir** com `Gerador_de_Itens_Magicos_2ed_OCR_alta_qualidade.docx` (Codex, item 62).

## Levantamento de estrutura (2026-06-05)
- ~23.622 parágrafos; cabeçalhos inúteis (só "Página N" + 1 título). Todo conteúdo em `Normal`.
- 288 páginas, 2 volumes: **Vol 1 = itens A–H**, **Vol 2 = itens H–Z**.
- Início do doc = **Sumário** (nome do item + nº de página, multi-coluna).
- Cada item: Nome + descrição (fragmentada em várias linhas) + frequentemente
  **tabela de bônus aleatório** (IP / 1d100 com faixas, ex: `+1 / 01-55`). ~237 tabelas 1d100.
- Estimativa: 400–600 itens individuais.

## OCR pesado (pior que os Anjos) — padrões observados
- `0` usado como "o"/"O" (artigo): `0 Monstro`, `0 Usuario`, `0 dano`.
- `urn`→um, `dane`→dano, `s6`→só, `toea`→toca, `tome`→torne, `fonnas/fonna`→formas,
  `Annadura`→Armadura, `pr6xim`→próxim, `mdependentemente`→independentemente, `dais`→dois.
- `<;` / `c;` / `c:;:` / `~;` → ç (ex: `Aben<;oado`, `Imolac;ao`, `Acelerac:;:ao`).
- `�` mojibake → á/í; `~` corrompido.
- Palavras coladas (`ArcoMagico`), `Areo`→Arco, quebras de frase em quase todo parágrafo.

## Decisões do usuário (2026-06-05)
1. **Escopo:** piloto por volume. Entregar **Volume 1 (A–H)** primeiro como `needs_review`,
   validar com o usuário, depois Volume 2.
2. **Tabelas 1d100:** campo **estruturado próprio** (extrair faixas → bloco renderizado
   como tabela), não embutir só como texto.
3. **Categorias:** **lista única alfabética** — uma categoria "Itens Mágicos", todos os
   itens em ordem alfabética (como o sumário).

## Fronteira mapeada (2026-06-05) — via `scripts/analyze_itens_magicos.py`
- Paginação OCR "Página N" é monotônica 1..288 (sem reinício) → âncora confiável.
- pg 1–4: capa/créditos/introdução. pg 5–10: **Sumário** (~49% linhas-número).
  pg 11–12: "Adaptando" + tabelas comparativas. pg 13–17: regras (Magia/Testes/Conversão).
- **Corpo dos itens: pg 18 (A: "Abóbora em Carruagem") até pg 271 (Z: "Zarabatana Tellers").**
- pg 272+: "Tabelas de Sorteio" (apêndice). pg 280: índice final. pg 283–287: propaganda+OGL.
- **Fronteira A–H / H–Z:** itens H terminam em **pg 146** (Hóstia dos Cruzados);
  **pg 147** começa o I (Incenso de Captura de Espíritos, título quebrado em 2 linhas).
- **VOLUME 1 (entrega 1) = páginas 18–146** (A–H). Volume 2 = pg 147–271 (I–Z).
- Títulos de item frequentemente quebrados em 2 linhas (ex.: "Incenso de Captura"/"de
  Espíritos") — reconstruir. Muitos itens têm subtítulos internos (Personalidade, Os
  Espíritos, Capacidade) que NÃO são itens.

## Plano de execução
1. [x] Delimitar no corpo onde termina o Vol 1 (A–H) e começa o Vol 2. → pg 18–146.
2. [ ] Estender `requiem_clean.py` (aditivo) com os padrões de OCR acima — avisar no handoff.
3. [ ] Limpar TODO o texto do Vol 1 antes de categorizar.
4. [ ] Parsear itens: nome + descrição + tabela 1d100 estruturada.
5. [ ] Gerar `data/pilot/guia-de-itens-magicos.json` (Vol 1).
6. [ ] Renderização da tabela 1d100 em `docs/assets/app.js` (aditivo — avisar handoff).
7. [ ] `build_pilot_index.py` + `validate_data.py` + `node --check app.js`.
8. [ ] Auditar JSON publicado + amostras reais. `needs_review` só após checklist.

## Arquivos compartilhados que vou tocar (aditivo)
- `scripts/requiem_clean.py` — novos padrões de OCR (substituições adicionais).
- `docs/assets/app.js` — renderização do bloco estruturado de tabela 1d100.
