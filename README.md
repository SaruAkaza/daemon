# Daemon Tools

Repositorio para transformar a biblioteca em `Livros/` em uma referencia digital pesquisavel, inspirada no modelo do 5e.tools.

## Objetivo

O 5e.tools organiza conteudo de RPG como entidades filtraveis, com busca, filtros, fontes e paginas de detalhe. Este repositorio usa essa arquitetura como inspiracao, mas a taxonomia e os dados sao do sistema Daemon/Trevas presente na pasta `Livros`.

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
- `docs/architecture/` — regras e arquitetura
- `docs/reference/` — regras editoriais e modelo de dados
- `coordination/` — estado operacional e coordenação

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

7. Publicar os dados consumidos pelo GitHub Pages:

   ```powershell
   python scripts/build_github_pages_site.py
   ```

## GitHub Pages

O explorador estatico fica em `docs/index.html`.

Para publicar no GitHub:

- Em Settings > Pages, escolha `Deploy from a branch`.
- Branch: `main`.
- Folder: `/docs`.
- Antes de subir alteracoes de dados, rode:

  ```powershell
  python scripts/build_area_catalog.py
  python scripts/build_github_pages_site.py
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

O workflow `Validate data` executa testes, validacao dos JSONs, cobertura dos livros, rebuild do catalogo e verifica se `data/areas`, `data/index/area-summary.json` e `docs/assets/data` ficaram sincronizados.

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
