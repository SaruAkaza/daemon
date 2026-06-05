# Handoff — Claude

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
