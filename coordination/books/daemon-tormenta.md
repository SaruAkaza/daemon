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

## Taxonomia FINAL (2026-06-06)
| Categoria | Conteúdo | Páginas |
|---|---|---|
| `racas` | 14 raças, TODAS com Custo explícito (Custo+Idade+Atributos+Vantagens+Desvantagens+Idiomas+desc) | 25–38 |
| `kits` | Profissões (Custo/Restrições/Aprimoramentos/Perícias/Armas e Armaduras/Especial+desc+epígrafe) | 42–68 |
| `aprimoramentos` | Vantagens/desvantagens `N pontos:` (Custo antes da Descrição) | 91–104 |
| `magias` | ~19 especialidades místicas (criação de itens mágicos + metamagia), Nome+[Custo]+Descrição. **Decisão do usuário: "trate como magia".** | 114–116 |
| `manobras_combate` | Ataque Poderoso, Fúria, Desarme, Tiro Certeiro… Nome+[Custo]+Descrição | 119–122 |
| group `regras` | criação de personagem, atributos, combate, sistema de magia (Caminhos/Círculos/Focus) | 4–24 + dispersas |

- 14 raças confirmadas (pg25 Humanos … pg38 Troglodita), todas com `Custo:`.
- Perícias com `[ATRIBUTO]` (Esquiva [AGI]) NÃO são entidades de custo — são a lista de
  perícias (regras). Distinguir `[N]`(custo) de `[ATRIBUTO]`.
- Footer a remover em toda página: `TORMENTA RPG - SISTEMA Daemon - VERSÃO DE THIAGO
  "MESTRE KWAN" RODRIGUES` (às vezes concatenado a texto real → split + strip).

## (Histórico) Decisões anteriores
- **Categorias finais:** `racas`, `kits`, `aprimoramentos` + 1 group `regras/sistema`.
- **MAGIAS: NÃO há entidades catalogáveis.** Reinspeção a fundo (pg 8, 63–70, 129–135):
  o livro traz só as REGRAS do sistema de magia (Caminhos + Formas gerativos, Círculos,
  Focus, Componentes/Fetiche/Gestos, Sustentáveis/Permanentes, conjuração). Não existe
  lista/ficha de feitiços (nome+Caminho+Círculo+Custo+Efeito). As "Magias Iniciais" em
  kits (Força Mágica, Detecção de Magia…) são só nomes recebidos, sem ficha. → Magia
  entra como REGRAS no group, não como categoria de entidades. (Fiel ao livro; protocolo:
  não inventar entidades.)
- **Regras:** 1 group "Regras/Sistema" (criação de personagem, atributos, combate, magia).
- **Raças:** verificar Custo no texto; só adicionar Custo se explícito.

## (Histórico) A decidir com o usuário (categorização/escopo)
1. Escopo: livro inteiro vs piloto por capítulo (Raças → Kits → Aprimoramentos → Magias)?
2. Categorias propostas: `lore/regras` (1 group), `racas`, `kits`, `aprimoramentos`, `magias`,
   e possivelmente `criaturas` (se houver bestiário).
3. Regras de criação de personagem (Passos 1–12, descrições de atributos): incluir como
   lore/regras ou descartar? (são regras, não entidades).
4. Raças: têm `Custo`? (catalogar Custo só se o livro explicitar custo de compra/uso).

## Plano (após decisões)
1. [x] Mapear fronteiras exatas de cada capítulo por página.
2. [x] Limpar texto (fix_ocr leve + remover footer + join_body).
3. [x] Parsear entidades por categoria.
4. [x] Gerar `data/pilot/daemon-tormenta.json`.
5. [x] build_pilot_index + validate_data + node --check; auditar.

## RESULTADO (2026-06-06) — entrega 1 (entidades), status needs_review
- **223 entidades**: racas 14, kits 43, aprimoramentos 117, magias 19, manobras_combate 30.
- Scripts: `scripts/build_daemon_tormenta.py` (parser) + `scripts/analyze_daemon_tormenta.py`
  (diagnóstico read-only).
- Pipeline: build OK, build_pilot_index (23 fontes), validate_data OK, node --check OK,
  data/pilot == docs/assets/data/pilot. JSON validado no navegador (fetch + checagem de
  campos): 223 seções, 5 áreas, 0 issues estruturais — app.js carrega sem erro.
- Bloco **Custo antes de Descrição** em todas as categorias (regra de ouro). Raças com Custo
  explícito. Magias = especialidades místicas (decisão "trate como magia").

## PENDÊNCIAS (declaradas, p/ revisão)
1. **Group de Regras NÃO incluído** (decisão do usuário: "publicar entidades agora; regras
   depois"). `groups: []`. Próxima etapa: criar group lore (criação de personagem,
   atributos, combate, sistema de magia) pg 4–24 + dispersas.
2. **Raça Humanos**: campo "Idiomas" engloba início da descrição — o OCR não pôs ponto após
   "Valkar"; sem terminador não dá pra cortar com segurança. (13/14 raças OK.)
3. **3 kits com custo plural sem número** (OCR perdeu o dígito), marcados `[?] pontos`:
   Invocador Arcano, Clérigo de Marah, Clérigo de Tanna-Toh. (8 casos "ponto" singular
   foram reconstruídos com segurança p/ "1 ponto".)
4. **Acentos esporádicos / `0`→o**: OCR bom mas com perdas pontuais; `causa 0 dano`→`causa o
   dano` pode ocorrer (0 como artigo vs numeral sem count-noun). Revisar na leitura.
5. **App: hub de categorias aparece vazio no estado inicial** (dropdown mostra categorias de
   um NPC, não as áreas globais). Parece PRÉ-EXISTENTE (não toquei app.js/index.html; único
   erro de console = favicon 404; meu JSON valida 100%). Investigar à parte antes do `done`.
