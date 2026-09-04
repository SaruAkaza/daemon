# Taxonomia Canônica do Sistema Daemon Tools

Este documento consolida a taxonomia oficial de dados e as categorias canônicas utilizadas para classificação, segmentação e navegação no acervo do **Daemon Tools**.

---

## 1. Categorias Canônicas de Entidades e Conteúdo

| Categoria (`category`) | Nome Descritivo | Significado | Exemplos | O que NÃO Pertence |
| :--- | :--- | :--- | :--- | :--- |
| **`source`** | Fonte / Obra | Livro, suplemento, módulo básico, netbook, revista ou documento original. | *Trevas 3.0*, *Grimório*, *Inquisição*, *Spiritum*, *Anime RPG - Powers*. | Capítulos isolados ou fragmentos de texto dentro do livro. |
| **`core_rule`** | Regra Base | Mecânicas fundamentais do sistema: testes de porcentagem (1d100), testes de atributos, dano, testes de resistência, evolução de personagem e regras de convivência. | "Regra base - Trevas", Teste de Perícia, Regras de Fadiga, Cálculo de PV/IP. | Regras específicas de combate tático avançado ou manobras isoladas. |
| **`attribute_skill`** | Atributos e Perícias | Atributos primários (CON, FR, DEX, AGI, INT, WILL, PER, CAR), perícias gerais, especializações e testes situacionais. | Perícia Armas Brancas, Perícia Ocultismo, Teste de Força de Vontade. | Aprimoramentos que concedem bônus fixos a perícias sem serem a perícia em si. |
| **`combat`** | Combate e Manobras | Mecânicas operacionais de combate: iniciativa, turnos, esquiva, bloqueio, dano localizado, manobras de combate desarmado/armado. | Tabela de Armas em Combate, Manobra Desarme, Golpe Giratório, Sequência Rápida. | Descrições puramente narrativas de armas ou itens de equipamento. |
| **`character_option`** | Opções de Personagem / Aprimoramentos | Aprimoramentos positivos, aprimoramentos negativos, vantagens, desvantagens, bênçãos e maldições com custo em pontos. | Bruto Insano (2 pts), Ciborgue (3 pts), Caçador Sobrenatural (2 pts), Sentidos Aguçados. | Kits com exigência obrigatória de perícias ou raças sem custo explícito. |
| **`kit_class`** | Kits e Classes | Arquétipos de personagem, profissões, ordens, kits de aventureiro e classes de prestígio que exigem custo e/ou lista de perícias. | Ferreiro Anão, Caçador de Bruxas, Assassino da Máfia, Templário. | Aprimoramentos conceituais sem custo em perícias. |
| **`race_lineage`** | Raças e Linhagens | Espécies, raças fantásticas, linhagens sobrenaturais, famílias de vampiros, castas de anjos e povos. | Anão, Elfo, Vampiro Lamia, Casta dos Alastores, Fantasma, Revenante. | NPCs individuais que pertençam àquela raça. |
| **`power_magic`** | Poderes e Vias Místicas | Poderes sobrenaturais estruturados por níveis, poderes de fé, poderes psíquicos, mutações e disciplinas. | Pirocinese (Nível 1 a 6), Fé Inabalável, Poderes Abissais, Domínio das Sombras. | Magias isoladas que pertençam a grimórios ou caminhos formais de feitiçaria. |
| **`ritual_spell`** | Magias e Rituais | Magias, encantamentos, rituais herméticos e evocações divididos por Caminho e Círculo. | Bola de Fogo (Fogo 3), Círculo de Proteção, Invocação de Mortos, Ritual de Banimento. | Mecânicas gerais de como funciona o sistema de magia (pertencem a `core_rule`). |
| **`item_equipment`** | Itens e Equipamentos | Armas brancas, armas de fogo, armaduras, veículos, artefatos mágicos, poções e tralha de aventura. | Espada Longa, Pistola 9mm, Armadura de Placas, Anel da Invisibilidade, Veículo Blindado. | Manobras de combate que utilizam o item. |
| **`creature_npc`** | Criaturas e NPCs | Fichas e perfis de monstros, animais, demônios, anjos, mortos-vivos e personagens notáveis. | Conde Straud, Gárgula de Pedra, Lobo da Noite, Inquisidor Mor. | Poderes globais para criação de personagens de jogadores. |
| **`setting_lore`** | Cenários e Lore | Geografia mística, história do universo, organizações, cultos, panteões e cronologia. | "Cenário - Vampiros Mitológicos", Ordem dos Templários, História de Arkanum. | Biografias completas de NPCs (ficam em `creature_npc`). |
| **`adventure`** | Aventuras e Campanhas | Módulos de aventura pronta, ganchos narrativos, cenas, mapas e encontros estruturados. | Campanha Épica de Trevas, O Mistério de Santa Cruz. | Lore geral de cenário sem estrutura de aventura. |
| **`table_generator`** | Tabelas e Geradores | Tabelas aleatórias de apoio, geradores de encontros, clima e nomes. | Tabela de Reações, Tabela de Nomes Élficos, Gerador de Encontros Urbanos. | Tabelas de atributos operacionais que componham regras base. |

---

## 2. Mapeamento entre Categorias e Áreas de Navegação (`data/areas/`)

A interface do usuário agrupa essas categorias em **Áreas Navegáveis** otimizadas para consulta rápida inspirada no 5e.tools:

- `regras_base` ── consome `core_rule` e `attribute_skill`
- `aprimoramentos` ── consome `character_option`
- `kits` ── consome `kit_class` (tipo `kit`)
- `classes` ── consome `kit_class` (tipo `classe` ou `prestigio`)
- `racas` ── consome `race_lineage` (espécies e aprimoramentos raciais)
- `linhagens` ── consome `race_lineage` (variações sobrenaturais)
- `poderes` ── consome `power_magic`
- `magias` ── consome `ritual_spell` (estruturadas por Caminho)
- `rituais` ── consome `ritual_spell` (rituais herméticos)
- `manobras_combate` ── consome `combat`
- `itens_equipamentos` ── consome `item_equipment`
- `criaturas_npcs` ── consome `creature_npc`
- `cenarios_lore` ── consome `setting_lore`
- `aventuras` ── consome `adventure`
- `tabelas` ── consome `table_generator`
