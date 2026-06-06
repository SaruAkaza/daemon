# Handoff — Claude

## 2026-06-05 (tarde) — Guia de Itens Mágicos
- Reivindiquei `Guia_de_Itens_Magicos_OCR_alta_qualidade.docx` (lista Claude, item 6).
  Contrato: `coordination/books/guia-de-itens-magicos.md`. **NÃO é** o
  `Gerador_de_Itens_Magicos_2ed` (esse é teu, Codex).
- Integrei `origin/main` no `claude-pilots` (teus commits de coordenação + archonan order).
  Conflitos archonan.json/index.html resolvidos a favor da TUA versão (eram mudanças
  convergentes; `build_archonan_pilot.py` ficou idêntico nos dois lados). Índice regenerado
  (22 fontes), validate_data OK, app.js OK.
- **AVISO (arquivos compartilhados):** vou editar de forma ADITIVA:
  - `scripts/requiem_clean.py` — novos padrões de OCR (`0`→o contextual, `urn`→um, ç
    multi-variante `<;`/`c;`/`c:;:`, `fonnas`→formas etc.). Não removo nada do existente.
  - `docs/assets/app.js` — renderização de um bloco estruturado de tabela 1d100 (bônus
    aleatório de itens). Aditivo.
  Se for integrar esses, faz merge antes.
- Escopo combinado com o usuário: entrego **Volume 1 (A–H)** primeiro como `needs_review`.
- **DAEMON TORMENTA — entrega 1 publicada (needs_review):** 223 entidades (racas 14,
  kits 43, aprimoramentos 117, magias 19, manobras_combate 30). Scripts novos:
  `build_daemon_tormenta.py`, `analyze_daemon_tormenta.py`. Pipeline OK (índice 23 fontes).
  Group de Regras fica p/ etapa 2 (decisão do usuário). Pendências em
  `coordination/books/daemon-tormenta.md`.
  - **Editei `scripts/requiem_clean.py` de novo (aditivo):** refinei `_ZERO_ART_RE` p/ não
    converter `0`→o antes de count-noun (`0 pontos` preservado). Anjos seguem intactos
    (normalize não chama fix_ocr). Se for integrar, faz merge.
- **REVERSÃO:** `Guia_de_Itens_Magicos` → status `blocked` (movido p/ Livros/word/corrigir). OCR severamente degradado:
  Vol1 com ~99% dos acentos perdidos e 39% das palavras irreconhecíveis. Estrutura já
  mapeada (pg 18–146 = Vol1) e `fix_ocr()` criado, mas catalogar este texto = retrabalho
  garantido. Aguardando fonte de melhor qualidade. Decisão do usuário: mover p/ correção
  e seguir adiante.
- **Triagem de OCR dos próximos candidatos** (palavras desconhecidas pelo dic pt = proxy
  de degradação; <15% é bom):
  - Daemon_Tormenta: 8.1% ✅ (melhor)
  - Demonio_O_Preço_do_Poder: 16.3% ✅
  - Trevas_Campanha_Épica: 17.6% ✅
  - Neokosmos: 28.0% ⚠️
  - Trevas_3_0: 88.6% ❌  | Supers: 91.3% ❌  (OCR inutilizável, bloquear ao chegar a eles)
  Lição: **triar OCR antes de reivindicar** (uso `scripts/analyze_itens_magicos.py` adaptado).

## 2026-06-05
- Worktree isolado: `daemon-claude` (branch `claude-pilots`). **Só trabalho aqui.**
- **CORREÇÃO**: li `book_assignments.md` do Codex. `Ark_a_nun - Bel Kalaa` é do **Codex**
  (item 10). **Devolvi** — não vou pegá-lo. Removi o contrato e a entrada do meu queue.
- Minha atribuição: lista "Claude" do `book_assignments.md` + todos os Anjos (status `hold`
  até liberação). Próximo livro meu: aguardando você liberar (Anjos em hold) ou começo pela
  lista Claude (ex.: `Trevas_3_0` / `Guia_de_Itens_Magicos`, menores primeiro).
- Livros que tratei e estão em `needs_review` (aguardando validação visual do usuário):
  anjos-angelicos-sicarios, anjos-requiem-de-fe, anjos-cacadores-alados, anjos-jyhad-faces-da-fe.
  **Não mexer nesses 4** sem combinar.
- Toquei em arquivos compartilhados: `scripts/requiem_clean.py` (adicionei
  ligaduras + `collapse_spaced_letters`) e `docs/assets/app.js` (filtros Caminho/Círculo,
  agrupamento de magias por Caminho, labels kit/magia/manobra/classe/character).
  Se for editar esses, faça `git pull`/merge antes.
- Índice: o gerador **já existe** (`scripts/build_pilot_index.py`) — corrigido, não vou
  criar outro. Padronizei o fluxo no README para ambos rodarem ele +
  `validate_data.py` + `node --check app.js` antes de publicar. Verifiquei: gera 22
  fontes, validação passou.

## Pergunta ao Codex
- Você cria `coordination/queue/codex.json` e `coordination/handoff/codex.md`?
  (deixei o README explicando o formato per-agente para não conflitarmos).
- Confirma branch própria por livro (`book/<livro>`)? Eu venho usando `claude-pilots`
  como guarda-chuva; migro para `book/ark-a-nun` no próximo.
