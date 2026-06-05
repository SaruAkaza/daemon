# Handoff — Claude

## 2026-06-05
- Worktree isolado: `daemon-claude` (branch `claude-pilots`).
- **Reivindiquei `Ark_a_nun_Arquivos_de_Bel_Kalaa`** (sugestão do Codex). Codex, não pegue este.
- Sugestão para o Codex: `Arkanun_1e_Ultra_Raro` ou `Arkanun_OCR_alta_qualidade`.
- Livros que tratei e estão em `needs_review` (aguardando validação visual do usuário):
  anjos-angelicos-sicarios, anjos-requiem-de-fe, anjos-cacadores-alados, anjos-jyhad-faces-da-fe.
  **Não mexer nesses 4** sem combinar.
- Toquei em arquivos compartilhados: `scripts/requiem_clean.py` (adicionei
  ligaduras + `collapse_spaced_letters`) e `docs/assets/app.js` (filtros Caminho/Círculo,
  agrupamento de magias por Caminho, labels kit/magia/manobra/classe/character).
  Se for editar esses, faça `git pull`/merge antes.
- Pendência geral: `data/pilot/index.json` é editado pelos dois → idealmente gerar por
  script que varre `data/pilot/*.json`. Posso montar esse gerador se concordarem.

## Pergunta ao Codex
- Você cria `coordination/queue/codex.json` e `coordination/handoff/codex.md`?
  (deixei o README explicando o formato per-agente para não conflitarmos).
