# Contexto Geral do Projeto Daemon Tools

Este documento fornece a visão arquitetural, stack técnica, estrutura de diretórios e fluxo operacional para qualquer agente ou colaborador que interaja com a base de código do **Daemon Tools**.

---

## 1. Visão do Produto

O **Daemon Tools** é uma plataforma digital para consulta e referência de todo o acervo bibliográfico do sistema de RPG Daemon/Trevas. Inspirado conceitualmente no modelo de navegação e busca do 5e.tools, o projeto organiza regras, aprimoramentos, poderes, kits, raças, magias, rituais, criaturas, cenários e tabelas em uma experiência estruturada, rápida e pesquisável, respeitando a taxonomia e as particularidades do sistema Daemon.

---

## 2. Stack Tecnológica Atual

O repositório mantém uma arquitetura leve, estática e determinística, sem frameworks pesados de frontend ou backends em execução contínua:

- **Frontend**: HTML5, CSS3 puro, JavaScript vanilla modular (`docs/assets/app.js`).
- **Dados**: Arquivos JSON estáticos e validados por JSON Schema (`Draft-07`).
- **Scripts e Automação**: Python 3 (PyMuPDF para extração de PDFs, python-docx para DOCXs, jsonschema para validação).
- **Testes e Qualidade**: pytest, pytest-cov, ruff e verificações de sintaxe com Node.js (`node --check`).
- **Hospedagem e Deploy**: GitHub Pages servindo diretamente o diretório `docs/`.

---

## 3. Estrutura do Repositório

```text
.
├── Livros/                  # Fontes originais imutáveis (PDFs, DOCXs organizados)
├── data/                    # Dados derivados e estruturados
│   ├── index/               # Inventário de fontes e resumos de catálogo
│   ├── books/               # Segmentação e cobertura de páginas por livro
│   ├── entities/            # Entidades normalizadas por categoria canônica
│   ├── areas/               # Camada de navegação por áreas temáticas
│   └── text/                # Texto bruto extraído (ignorado pelo Git)
├── docs/                    # Site estático publicado no GitHub Pages
│   ├── index.html           # Aplicação frontend principal
│   ├── assets/              # Scripts (app.js), estilos e assets estáticos
│   │   └── data/            # Dados JSON consumidos em tempo de execução pela interface
│   ├── architecture/        # Documentos fundamentais de arquitetura multiagente
│   ├── reference/           # Regras de catalogação canônicas e modelo de dados
│   ├── superpowers/         # Especificações e planos de capacidades
│   └── reports/             # Relatórios de auditoria, qualidade e cobertura
├── schemas/                 # JSON Schemas formais para entidades, segmentos e overrides
├── scripts/                 # Scripts determinísticos de extração, limpeza, build e validação
├── tests/                   # Suíte de testes automatizados em pytest
├── coordination/            # Protocolo legado de coordenação e handoffs (Codex/Claude)
└── .github/workflows/       # Workflows de CI no GitHub Actions
```

---

## 4. Fluxo de Trabalho e Pipeline Atual

O fluxo existente de processamento e publicação segue os seguintes passos:

1. **Inventário**: Mapeamento dos arquivos em `Livros/` gerando `data/index/sources.json`.
   ```bash
   python scripts/inventory.py
   ```
2. **Extração Textual**: Extração do texto bruto para `data/text/`.
   ```bash
   python scripts/extract_text.py
   ```
3. **Categorização e Segmentação**: Classificação inicial do conteúdo e segmentação por página.
   ```bash
   python scripts/categorize.py
   ```
4. **Verificação de Cobertura**: Garantia de que todas as páginas de cada livro foram mapeadas.
   ```bash
   python scripts/check_book_coverage.py
   ```
5. **Geração do Catálogo por Áreas**: Montagem dos dados em `data/areas/`.
   ```bash
   python scripts/build_area_catalog.py
   ```
6. **Publicação no Site**: Cópia e estruturação dos dados para `docs/assets/data/`.
   ```bash
   python scripts/build_github_pages_site.py
   ```

---

## 5. Comandos de Qualidade e Verificação

Antes de submeter qualquer alteração, os seguintes comandos devem ser executados para validar a integridade da base:

```bash
# Execução da suíte completa de testes automatizados
python -m pytest -q

# Validação dos arquivos JSON contra os schemas
python scripts/validate_data.py

# Verificação de cobertura total das páginas dos livros
python scripts/check_book_coverage.py

# Reconstrução do catálogo por áreas e sincronização do frontend
python scripts/build_area_catalog.py
python scripts/build_github_pages_site.py

# Verificação de sintaxe do JavaScript da interface
node --check docs/assets/app.js
```

---

## 6. Publicação e Consumo de Dados no Frontend

A aplicação hospedada no GitHub Pages (`docs/index.html`) opera de forma totalmente estática e do lado do cliente (client-side). Ela consome exclusivamente os arquivos JSON estruturados localizados em `docs/assets/data/`. Nenhuma rota de API dinâmica ou banco de dados externo é utilizado em tempo de execução.
