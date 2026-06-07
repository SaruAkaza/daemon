# Contrato — Daemon Medieval

- **Agente:** Claude (worktree `daemon-claude`, branch `claude-pilots`)
- **DOCX:** `Livros/word/Daemon_Medieval_OCR_alta_qualidade.docx`
- **source / pilot:** `daemon-medieval`
- **Reivindicado:** 2026-06-06 · Lista Claude item 18 (0.18 MB). Núcleo Daemon, cenário medieval.

## Qualidade de OCR
- **Melhor da fila** (triagem: 6.3% palavras desconhecidas, 13.6% acentos). Legível.

## Estrutura (levantamento 2026-06-06)
- 4.902 parágrafos; cabeçalhos só "Página N" (74 págs); conteúdo em `Normal`.
- Marcadores: 13 `Restrições:`, 16 `Perícias:`, 18 `Custo:`, 8 `Atributos:` (raças),
  128 menções "Aprimoramento", **103 "Caminho"** (magias?), 16 "Nível", 61 "Kit".
  Stat blocks: 38 `CON`, 40 `FR`, 50 `PV` (possível bestiário/NPCs).
- pg 5+: criação de personagem (regras + exemplos: Argos/Kroog/Darien).
- pg 22+: Aprimoramentos. pg 42: tabela de **equipamentos** (item + peso + preço).
- pg 61+: regras de combate/atributos (exemplos).

## A decidir (após mapear fronteiras)
- Categorias prováveis: `racas`, `kits`, `aprimoramentos`, `magias` (por Caminho?),
  `itens_equipamentos` (tabela de equipamentos), `criaturas_npcs` (se houver stat blocks),
  + group `regras`.
- Verificar se "Caminho" são magias enumeráveis (como no Réquiem) ou regra de sistema
  (como no Tormenta).
- Verificar se equipamentos viram entidades ou ficam em tabela/lore.

## Plano
1. [ ] Mapear fronteiras exatas por página.
2. [ ] Limpar texto (fix_ocr leve + footer + join_body).
3. [ ] Propor categorização ao usuário (ambiguidades reais).
4. [ ] Parsear + gerar `data/pilot/daemon-medieval.json`.
5. [ ] build_pilot_index + validate_data + node --check; auditar.
6. [ ] Sincronizar main (merge + ff + push).
