# Coordenação multi-agente (Codex + Claude)

O repositório é a fonte da verdade — os agentes não compartilham memória.
Protocolo para trabalharmos em paralelo **sem colisão**.

## Isolamento físico (git worktrees)
- **Codex**: `...\Repositorio\daemon` (branch própria, ex: `book/<livro>`)
- **Claude**: `...\Repositorio\daemon-claude` (branch `claude-pilots` ou `book/<livro>`)
- Cada agente edita arquivos no seu próprio diretório → sem sobrescrita em disco.
- Integração via merge no `main`.

## Regra de ouro
**Um livro por agente.** O `build_<livro>.py` e os JSONs daquele livro
(`data/pilot/`, `docs/assets/...`) são exclusivos de quem o reivindicou.

## Arquivos de coordenação (desenhados para NÃO conflitar)
Em vez de um arquivo compartilhado único, cada agente escreve **só no seu**:

- `coordination/queue/codex.json`  — fila/estado dos livros do Codex (só Codex edita)
- `coordination/queue/claude.json` — fila/estado dos livros do Claude (só Claude edita)
- `coordination/handoff/codex.md`  — recados do Codex (só Codex edita)
- `coordination/handoff/claude.md` — recados do Claude (só Claude edita)
- `coordination/books/<livro>.md`  — contrato do livro (de quem o trata)
- `coordination/catalog_rules.md`  — cartilha de regras (compartilhada; mudar com cuidado, append)

> Para saber o estado geral, leia AMBOS os `queue/*.json`.

## Status possíveis
`todo` · `in_progress` · `needs_review` · `approved` · `done` · `blocked`

## Antes de pegar um livro
1. Leia `queue/codex.json` e `queue/claude.json` — confirme que ninguém o tem.
2. Adicione a entrada no SEU `queue/<agente>.json` com `in_progress` e sua branch.
3. Crie `books/<livro>.md` (contrato) antes de codificar.

## Índice é GERADO (não editar à mão)
Já existe o gerador — **não criar outro**:
```
python scripts\build_pilot_index.py
```
Varre `data/pilot/*.json` (ignora index.json), gera `data/pilot/index.json` e
`docs/assets/data/pilot/index.json`, e copia os JSONs para docs. Após qualquer
merge de `main`, **rode de novo** para reconciliar o índice (saída determinística).

## Fluxo padrão (combinado com o Codex)
1. Trabalhar em **branch própria por livro** (`book/<livro>`), nunca direto no `main`.
2. Antes de começar livro novo: `git fetch` + integrar `main` (merge/rebase).
3. Antes de publicar/validar, rodar:
   ```
   python scripts\build_pilot_index.py
   python scripts\validate_data.py
   node --check docs\assets\app.js
   ```
4. Evitar os dois mexerem ao mesmo tempo em `docs/assets/app.js`,
   `scripts/requiem_clean.py` e regras globais — avisar no handoff.

## Arquivos compartilhados sensíveis (cuidado no merge)
`scripts/requiem_clean.py`, `docs/assets/app.js`. Mudanças aditivas; avisar no
handoff antes de editar. (`index.json` não conta — é gerado.)

## Checklist obrigatório antes de `needs_review`
- [ ] Texto revisado (OCR/dehifenização/ligaduras/espaçamento)
- [ ] Categorias conferidas
- [ ] Ordem dos blocos conferida
- [ ] JSON gerado (data/ e docs/ idênticos)
- [ ] Aplicação validada visualmente
- [ ] `validate_data.py` passou (se existir)
- [ ] DOCX movido para `Livros/word/feito`
- [ ] Commit separado

`done` só após validação do usuário.
