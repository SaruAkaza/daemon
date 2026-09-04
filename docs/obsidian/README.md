# Obsidian — Daemon Project Brain

Esta pasta adiciona uma camada de navegação em Obsidian ao repositório Daemon Tools.

## Como abrir
1. Abra o Obsidian.
2. Escolha **Open folder as vault / Abrir pasta como cofre**.
3. Selecione:
   `C:\Users\TI Prevent\Documents\Daemon Tools`
4. Abra `PROJECT-BRAIN.md`.

## Princípio
Não existe uma segunda documentação para o Obsidian.
O Vault usa os mesmos arquivos Markdown já versionados pelo Git.

## Plugins
Nenhum plugin comunitário é obrigatório. Os recursos nativos são suficientes:
- Graph View
- Backlinks
- Outgoing Links
- Search
- Properties
- Templates

## Git
Recomendação inicial: adicionar ao `.gitignore`:

```gitignore
.obsidian/
```

## Conteúdo novo
- Missões: `docs/missions/`
- Decisões: `docs/context/decisions/`
- Precedentes: `docs/context/precedents/`
- Notas de livros: `docs/context/books/`
- Índices Obsidian: `docs/obsidian/mocs/`
- Templates: `docs/obsidian/templates/`

## Regra contra duplicação
Se uma informação já existe em documento canônico, crie um link em vez de copiar a regra.
