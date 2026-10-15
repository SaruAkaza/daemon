# Daemon Tools

Repositorio para transformar a biblioteca em `Livros/` em uma referencia digital pesquisavel, inspirada no modelo do 5e.tools.

## Objetivo

O 5e.tools organiza conteudo de RPG como entidades filtraveis, com busca, filtros, fontes e paginas de detalhe. Este repositorio usa essa arquitetura como inspiracao, mas a taxonomia e os dados sao do sistema Daemon/Trevas presente na pasta `Livros`.

## Estado da consolidação

A integração de 2026-10-14 reuniu o pipeline, o frontend MVP, o catálogo ampliado,
o painel operacional e as correções de relações na `main` (PR #1).
Resultados, commits de origem, limites de publicação e trabalho restante estão
em [Consolidação técnica](docs/reports/2026-10-14-consolidation-validation.md).
Inventário e testes aprovados não significam que os 281 livros estejam revisados
ou autorizados para publicação.

A reconciliação das fontes atuais com o inventário histórico pode ser consultada
em `data/index/source-reconciliation.json`. O diagnóstico e a verificação são
somente de leitura: `python scripts/reconcile_sources.py` e
`python scripts/reconcile_sources.py --check`. Veja
[Reconciliação de fontes legadas](docs/reference/source-reconciliation.md).

O plano de migração em `data/index/source-migration-plan.json` registra as
mudanças propostas e as pendências de versões/páginas. A preparação de cópias
privadas para revisão usa `python scripts/prepare_source_migration.py --stage`;
veja [Preparação da migração](docs/reference/source-migration.md).

O motor privado da Release C controla fila, concorrência, checkpoints e retomada.
A demonstração com cinco livros sintéticos usa
`python -m scripts.orchestrator --demo --runtime-dir /tmp/daemon-demo --serve`.
Os executores do acervo real ainda precisam de integração e certificação. Veja
[Motor de lotes e aprovação privada](docs/reference/batch-orchestrator.md).

A extração real PDF/DOCX e a preparação de evidências para revisão podem ser
conectadas com `--adapters scripts.orchestrator.real_adapters:build_executors`.
O primeiro ensaio privado, Corondor, preservou 2.609 blocos e parou para revisão
de páginas/conteúdo visual. Veja [Extração real](docs/reference/real-extraction.md)
e [Resultados de Corondor](docs/reports/2026-10-15-real-extraction-corondor.md).

## Estrutura proposta

- `Livros/`: arquivos fonte originais.
- `data/index/sources.json`: inventario dos arquivos fonte.
- `data/entities/`: entidades extraidas e normalizadas.
- `data/areas/`: camada navegavel por areas, combinando entidades curadas e partes dos livros.
- `data/text/`: texto bruto extraido dos livros, ignorado pelo Git.
- `docs/`: site estatico do GitHub Pages.
- `docs/reference/`: notas de arquitetura e modelo de dados.
- `docs/reports/`: relatorios de auditoria, certificacao, extracao granular e revisao manual.
- `schemas/`: JSON Schemas para validar entidades.
- `scripts/`: automacoes de inventario, extracao e categorizacao.

## Coordenação agentic

- `AGENTS.md` — entrada para agentes
- `PROJECT-BRAIN.md` — entrada central de conhecimento (Obsidian Vault entry)
- `docs/architecture/` — regras e arquitetura
- `docs/reference/` — regras editoriais e modelo de dados
- `docs/obsidian/` — MOCs e templates do Daemon Project Brain
- `coordination/` — estado operacional e coordenação

## Project Brain / Obsidian

O repositório pode ser aberto diretamente como um Vault do Obsidian.

Página inicial:

`PROJECT-BRAIN.md`

O Obsidian é uma camada de navegação sobre a documentação versionada; ele não substitui Git nem cria uma segunda fonte da verdade.

## Fluxo de trabalho

1. Gerar inventario:

   ```powershell
   python scripts/inventory.py
   ```

2. Instalar dependencias de extracao:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Extrair texto dos livros:

   ```powershell
   python scripts/extract_text.py
   ```

4. Criar uma primeira categorizacao automatica:

   ```powershell
   python scripts/categorize.py
   ```

5. Verificar se cada livro lido teve todas as paginas destinadas a alguma parte:

   ```powershell
   python scripts/check_book_coverage.py
   ```

6. Gerar o catalogo por areas:

   ```powershell
   python scripts/build_area_catalog.py
   ```

7. Verificar os direitos antes de publicar os dados consumidos pelo GitHub Pages:

   ```powershell
   python scripts/build_github_pages_site.py --check-only
   ```

   A cópia integral exige manifestos de fonte válidos, vinculados ao inventário,
   com visibilidade pública e permissão `FULL_TEXT`. Após revisão e autorização
   da release, execute sem `--check-only`. Veja
   [Publicação dos JSONs legados](docs/reference/legacy-publication.md).

## GitHub Pages

O explorador estatico fica em `docs/index.html`.

Para publicar no GitHub:

- Em Settings > Pages, escolha `Deploy from a branch`.
- Branch: `main`.
- Folder: `/docs`.
- Antes de subir alteracoes de dados, rode:

  ```powershell
  python scripts/build_area_catalog.py
  python scripts/build_github_pages_site.py --check-only
  ```

O site usa apenas HTML, CSS, JavaScript e JSON estatico em `docs/assets/data/`.

## Qualidade e validacao

Instale as dependencias de desenvolvimento para rodar os testes locais:

```powershell
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

Comandos principais de verificacao:

```powershell
python -m pytest -q
python scripts/validate_data.py
python scripts/check_book_coverage.py
```

Antes de enviar mudancas de dados para o GitHub Pages, reconstrua o catalogo e os JSONs publicados:

```powershell
python scripts/build_area_catalog.py
python scripts/build_github_pages_site.py
```

O workflow `Validate` executa lint, testes Python/Node/Chromium, validação dos JSONs,
cobertura dos livros e sincronização dos dados existentes por leitura. O CI não
reconstrói nem publica conteúdo do acervo. Os publicadores de áreas e pilotos
bloqueiam cópia integral sem os manifestos de direitos descritos acima.

## Atualizacao apos editar `data/text/`

O site nao le `data/text/*.txt` diretamente. Quando um texto bruto for corrigido manualmente, use a rotina de sincronizacao para detectar os arquivos alterados e reconstruir as dependencias:

```powershell
python scripts/update_from_text_changes.py
```

Na primeira vez, ou quando quiser apenas criar uma linha de base sem reconstruir nada:

```powershell
python scripts/update_from_text_changes.py --init
```

Para deixar a rotina observando alteracoes enquanto voce edita:

```powershell
python scripts/update_from_text_changes.py --watch
```

Por padrao, a rotina atualiza `data/books`, `data/entities/source.json`, `data/areas` e `docs/assets/data`. Se a correcao no texto precisa atualizar tambem entidades certificadas como aprimoramentos, kits, racas, linhagens, poderes ou magias, rode:

```powershell
python scripts/update_from_text_changes.py --granular
```

Rituais ainda ficam separados; para incluir essa passada junto da granular:

```powershell
python scripts/update_from_text_changes.py --granular --include-rituais
```

## Regra de leitura

Cada lote deve ser tratado com cobertura total. Isso significa que todas as paginas do livro precisam estar representadas em `data/books/<livro>.json`, mesmo quando a pagina for capa, credito, ficha, tabela, continuacao de secao ou material de apoio. O texto bruto completo fica em `data/text/` e os JSONs versionados guardam a separacao, categorias, entidades e referencias de pagina.

## Categorias Daemon iniciais

- `source`: livro, suplemento, modulo, revista ou documento base.
- `core_rule`: regras centrais do sistema, testes, dano, evolucao e mecanicas gerais.
- `attribute_skill`: atributos, pericias, especializacoes e usos de testes.
- `combat`: iniciativa, ataques, defesa, armas em combate, dano e manobras.
- `character_option`: aprimoramentos, vantagens, desvantagens, poderes e opcoes de personagem.
- `kit_class`: kits, classes, caminhos, ocupacoes e arquetipos.
- `race_lineage`: racas, linhagens, especies, povos e variacoes sobrenaturais.
- `power_magic`: caminhos de magia, poderes misticos, poderes de fe, psiquismo e similares.
- `ritual_spell`: magias, rituais, efeitos, grimorios e listas de poderes.
- `item_equipment`: armas, armaduras, equipamentos, itens magicos, veiculos e objetos.
- `creature_npc`: criaturas, monstros, NPCs, entidades, anjos, demonios e mortos-vivos.
- `setting_lore`: ambientacao, mitologia, religiao, geografia, historia e organizacoes.
- `adventure`: campanhas, aventuras, cenarios prontos.
- `table_generator`: tabelas, geradores e material de apoio rapido.

## Observacao

Se os livros tiverem conteudo protegido por direitos autorais, mantenha o uso de texto integral restrito a um acervo privado/autorizado. Para um site publico, prefira metadados, indices, referencias de pagina e resumos autorizados.
