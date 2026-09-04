# Obsidian — Daemon Project Brain

Esta pasta integra a camada de navegação humana do Daemon Tools no Obsidian.

## Como abrir

1. Abra o Obsidian;
2. Escolha **Open folder as vault** (Abrir pasta como cofre);
3. Selecione a raiz do projeto:
   `C:\Users\TI Prevent\Documents\Daemon Tools`
4. Abra a página inicial:
   `PROJECT-BRAIN.md`

## Regra Fundamental

> **Git é a fonte da verdade. Obsidian é a interface de conhecimento.**

Não duplique regras documentadas. Se algo já existe em:
- `docs/architecture/`
- `docs/agents/`
- `docs/context/`
- `docs/reference/`

utilize `[[links]]` (wikilinks ou links relativos). Não copie o conteúdo da regra.

## Plugins e Recursos

Nenhum plugin comunitário é obrigatório. Utilize os recursos nativos do Obsidian:
- Graph View (Visualização gráfica de nós e conexões)
- Backlinks (Links bidirecionais reversos)
- Outgoing Links (Links de saída)
- Search (Busca textual e por propriedades)
- Properties (Propriedades/frontmatter estruturadas)
- Templates (Modelos de missões, livros, ADRs, precedentes e revisões humanas)

## Estrutura do Vault

- **Página Inicial**: `PROJECT-BRAIN.md`
- **MOCs (Maps of Content)**: `docs/obsidian/mocs/`
- **Templates**: `docs/obsidian/templates/`
- **Notas de Livros**: `docs/context/books/`
- **Missões**: `docs/missions/`
- **Decisões (ADRs)**: `docs/context/decisions/`
- **Precedentes**: `docs/context/precedents/`
