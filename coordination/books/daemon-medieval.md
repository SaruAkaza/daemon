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

## DECISÕES (2026-06-06)
- **Categorias:** `racas`, `kits`, `aprimoramentos`, `itens_equipamentos` + group `regras`.
- **Magias: NÃO catalogáveis** (reinspeção a fundo do Cap.9, pg 55–59): sistema gerativo
  (Formas Entender/Criar/Controlar × Caminhos Fogo/Terra/Água/Ar/Luz/Trevas), Pontos de
  Magia/Fé. Texto explícito (pg 58): "Um Feiticeiro não começa com uma lista de magias
  escritas"; "ficha de magias no final" = planilha em branco. Vai como REGRAS no group.
- **Group de Regras: incluir nesta entrega** (decisão do usuário). Cobrir criação de
  personagem, atributos, sistema de magia, combate/perigos.
- Formato de raça/kit/aprimoramento = mesmo do Tormenta (reaproveitar parser).
- Fronteiras: racas pg 10–12, kits pg 13–19(+31), aprimoramentos pg 22+, equipamentos
  pg 42–47 (itens com descrição). Magia pg 55–59 (regras).

## (Histórico) A decidir (após mapear fronteiras)
- Categorias prováveis: `racas`, `kits`, `aprimoramentos`, `magias` (por Caminho?),
  `itens_equipamentos` (tabela de equipamentos), `criaturas_npcs` (se houver stat blocks),
  + group `regras`.
- Verificar se "Caminho" são magias enumeráveis (como no Réquiem) ou regra de sistema
  (como no Tormenta).
- Verificar se equipamentos viram entidades ou ficam em tabela/lore.

## Plano
1. [x] Mapear fronteiras exatas por página (via capítulos).
2. [x] Limpar texto (fix_ocr + footer "Daemon Medieval" + join_body).
3. [x] Categorização decidida com o usuário.
4. [x] Parsear + gerar `data/pilot/daemon-medieval.json`.
5. [x] build_pilot_index (25 fontes) + validate_data + node --check; auditar (navegador).
6. [ ] Sincronizar main (merge + ff + push).

## RESULTADO (2026-06-06) — status needs_review
- **230 seções**: racas 6, kits 12, aprimoramentos 104, itens_equipamentos 108,
  + group `regras_base` (6 blocos: conceitos, criação, atributos, perícias, magia,
  testes/combate).
- Parser `scripts/build_daemon_medieval.py` (derivado do Tormenta; racas/kits por whitelist
  + âncora Custo; equipamentos por padrão `Nome: descrição`).
- Custo antes de Descrição em todas as categorias. Raças e kits com Custo explícito.
- Validado no navegador: hub popula (correção do Codex ativa), JSON carrega, 5 áreas+group.

## PENDÊNCIAS (declaradas)
1. Alguns aprimoramentos com nome truncado por OCR (ex.: "Hábitos Detestáveis" virou
   "Detestáveis", "Mania de Perseguição"→"Mania", "Ódio"). Filtrei os 4 piores
   (`_ENH_REJECT`); pode haver outros truncamentos menores — revisar na leitura.
2. Equipamentos: catalogadas as descrições nomeadas (Cap.8); a tabela de preços
   (colunas fragmentadas) ficou de fora.
3. Group de regras: cobertura por blocos temáticos, não transcrição exaustiva
   (exemplos/trechos fragmentados omitidos).
