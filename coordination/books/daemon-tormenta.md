# Contrato — Daemon Tormenta

- **Agente:** Claude (worktree `daemon-claude`, branch `claude-pilots`)
- **DOCX:** `Livros/word/Daemon_Tormenta_OCR_alta_qualidade.docx`
- **source / pilot:** `daemon-tormenta`
- **Reivindicado:** 2026-06-05
- Lista Claude item 11 (0.26 MB). Crossover Tormenta (Arton) no sistema Daemon.
  Versão de Thiago "Mestre Kwan" Rodrigues.

## Qualidade de OCR
- **Boa** (triagem: 8.1% palavras desconhecidas, melhor da fila). Acentos preservados.
- Ruído a descartar: cabeçalho/rodapé repetido
  `TORMENTA RPG - SISTEMA Daemon - VERSÃO DE THIAGO "MESTRE KWAN" RODRIGUES`.
  Sumário OCR com lixo (`Conceitos BASICOS 20.2 ee 7`, `Pontos de FO@.wn`).

## Estrutura (levantamento 2026-06-05)
- 8.236 parágrafos; cabeçalhos só "Página N" (181 págs); conteúdo em `Normal`.
- pg 4–6: sumário + introdução. pg 8–20: criação de personagem (Passos 1–12),
  conceitos básicos, atributos (CON/DES/AGI/INT/WILL/CAR/PER), regras de teste.
- pg ~25+: **Raças** de Arton (Humanos; Anões `+2 CON -2 AGI`; Elfos `+2 DES -2 CON`; ...).
- pg ~49: **Kits/Profissões** (ex.: Lanceiro — `Custo: 1 ponto de aprim. / 185 pts perícias`,
  Restrições, Perícias, Aprimoramento, Armas e Armaduras, Especial).
- pg ~98: **Aprimoramentos** (vantagens/desvantagens: Cleptomaníaco -2, Código de Honra -1...).
- **Magias** por Caminho (29 "Caminho", 10 "Círculo").
- Marcadores: 77 `Custo:`, 46 `Perícias:`, 42 `Restrições:`, 38 `CON ` (stat blocks).

## A decidir com o usuário (categorização/escopo)
1. Escopo: livro inteiro vs piloto por capítulo (Raças → Kits → Aprimoramentos → Magias)?
2. Categorias propostas: `lore/regras` (1 group), `racas`, `kits`, `aprimoramentos`, `magias`,
   e possivelmente `criaturas` (se houver bestiário).
3. Regras de criação de personagem (Passos 1–12, descrições de atributos): incluir como
   lore/regras ou descartar? (são regras, não entidades).
4. Raças: têm `Custo`? (catalogar Custo só se o livro explicitar custo de compra/uso).

## Plano (após decisões)
1. [ ] Mapear fronteiras exatas de cada capítulo por página.
2. [ ] Limpar texto (fix_ocr leve + remover cabeçalho repetido + join_body).
3. [ ] Parsear entidades por categoria.
4. [ ] Gerar `data/pilot/daemon-tormenta.json`.
5. [ ] build_pilot_index + validate_data + node --check; auditar.
