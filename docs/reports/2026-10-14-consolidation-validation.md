# Consolidação técnica do Daemon — 2026-10-14

Status: `NEEDS_HUMAN_REVIEW`.

Este relatório documenta a consolidação do código existente. Ele não certifica
os 281 livros como concluídos e não concede autorização de publicação de conteúdo.

## Fontes integradas

Base pública consultada: `main`, commit
`12a47d9f8b2c653830b78d305fcd8e9b9f93f50a`.

| Linha de desenvolvimento | Commit de origem | Resultado |
| --- | --- | --- |
| Pipeline, frontend MVP e planos | `35e60d434d0625cd94943f83fe402b1b78f13aa5` | Incluído |
| Release A: acervo e catálogo | `2646bdf370e820a3d5af156f57d32727b97ceb63` | Incluído |
| Release B: operações e revisão | `2559e63fa48c20b3145adcb2e6c9b002500d5617` | Incluído |
| Correções de relações | `a5ef8d60c6ea3cf2314eafa96b383d2e57fe7274` | Incluído |

Merge de consolidação: `afdefd7103a2679a1a63ec63ec45aa10877f8256`.
Todos os commits de origem foram confirmados como ancestrais desse merge.
As cópias originais foram preservadas; seus diretórios de trabalho não foram usados
como destino de edição.

## Ajustes necessários à integração

- Resolvido o conflito de `LocalPreviewProjector`: as relações canônicas alimentam
  tanto o índice legado quanto o contrato novo do site. A escrita continua usando
  staging e promoção atômica, depois da validação.
- Adicionado teste de regressão para impedir que a integração descarte relações
  canônicas ou retome escrita antecipada do índice.
- Removida a dependência do teste de inventário de um runtime privado instalado
  na máquina do desenvolvedor. Testes Python e de navegador compartilham agora
  bundles sintéticos com hashes e registros de revisão explícitos.
- Corrigido o vínculo da solicitação sintética de revisão com seu job, sem
  enfraquecer a verificação de autoridade do leitor.
- Substituído o teste que aceitava `scrollTop >= 0` por testes com 96 entradas e
  conteúdo longo. Eles exigem movimento efetivo após o uso da roda do mouse e
  acesso ao último resultado/parágrafo.
- O workflow passa a instalar Chromium, executar os testes dos módulos Node e
  verificar a sintaxe de todos os arquivos JS e MJS do frontend.

## Validação local

Ambiente: Windows, Python 3.12.14, pytest 8.4.2, Playwright 1.64.0 e Node 24.19.0.
O CI mantém Python 3.12 e Node 20; sua execução sobre o SHA final é uma evidência
separada dos resultados locais.

| Verificação | Resultado |
| --- | --- |
| Suíte Python, exceto navegador | 805 aprovados, 2 ignorados |
| Suíte de navegador Chromium | 28 aprovados |
| Testes de rolagem, contidos na suíte de navegador | 8 aprovados |
| Testes dos módulos Node | 46 aprovados |
| Validação dos JSONs e schemas existentes | PASS |
| Cobertura de páginas | 281 livros, nenhum erro |
| Sintaxe do frontend | 6 arquivos JS/MJS, PASS |
| Sincronização das áreas publicadas | 14 arquivos idênticos e resumo idêntico |
| Lint dos arquivos Python ajustados na consolidação | PASS |

Os dois testes ignorados exigem criação de symlinks, indisponível com as permissões
Windows usadas na validação. Eles permanecem na suíte; não foram removidos ou
transformados em aprovação.

Comandos principais:

```text
python -m pytest -q --ignore=tests/frontend
python -m pytest tests/frontend -q
node --test tests/frontend/*.test.mjs
python scripts/validate_data.py
python scripts/check_book_coverage.py
node --check <cada arquivo .js e .mjs em docs/assets>
```

No Windows, os testes usaram diretórios temporários curtos e externos ao checkout
para evitar o limite de comprimento de caminhos. Fixtures novas contêm somente
conteúdo sintético. Nenhum runtime real de Animalidade foi copiado para o checkout.

## Integridade dos dados e fronteira de publicação

A comparação com a base pública confirma zero alterações em `data/`, `Livros/`
e `docs/assets/data/`. A consolidação acrescenta código, contratos e testes já
existentes nas linhas de desenvolvimento; ela não aplica uma migração ao acervo.
Os relatórios de migração incorporados são registros históricos da branch de
origem, e não decisões novas tomadas durante esta consolidação.

O script legado `build_github_pages_site.py` ainda copia os dados das áreas sem
aplicar a política nova de direitos. Portanto, estes resultados técnicos não
autorizam reconstrução e publicação de conteúdo por esse caminho. A autorização
de uma release pública continua pendente de revisão específica do fluxo de
publicação e dos direitos de cada fonte.

## Trabalho restante

1. Revisar esta consolidação e a execução de CI correspondente ao SHA proposto.
2. Realizar aceite humano da interface e registrar a decisão, mantendo separadas
   a aprovação técnica do código e a autorização de publicação dos livros.
3. Reconciliar os registros antigos de revisão, OCR, quarentena e referências
   brutas com o inventário atual, sem promover candidatos automaticamente.
4. Integrar a política de direitos ao fluxo efetivo de publicação.
5. Executar a Release C, se o escopo desejado incluir processamento contínuo de
   vários livros; seu motor de batch permanece planejado.

Referências normativas: `docs/architecture/constitution.md`,
`docs/architecture/pipeline.md` e
`docs/context/decisions/ADR-0003-development-fork-and-upstream-release-model.md`.
