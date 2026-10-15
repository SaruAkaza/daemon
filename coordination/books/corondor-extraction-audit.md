# Corondor — auditoria privada de extração

Responsável: Codex. Branch: `codex/real-extraction-review-adapters`.
Estado: `needs_review`, 2026-10-15. A integração de código está em validação;
o livro não foi aprovado.

## Escopo

- Fonte física: `Livros/word/feito/Corondor.docx`.
- SHA-256: `57dd236dd3e0a36888cc88f16a4d60f0121c9159c866a96475633e9fa2a98367`.
- ID físico: `file-<SHA-256>` completo; não usar o ID legado como alias aprovado.
- Atribuição histórica ao Codex: `coordination/book_assignments.md`, item 2.
- O manifesto permanece `UNKNOWN`, `private`, `NOT_PUBLIC`.

Conectar extração determinística e pacote de revisão ao motor da Release C,
preservando todos os parágrafos/tabelas e seus localizadores XML. O ensaio usa
um runtime externo ao checkout e mantém fonte, piloto, inventário e assets
públicos intactos. Testes de PDF/DOCX usam somente conteúdo sintético próprio.

## Gates

SHA-256 deve corresponder ao arquivo original. Preservar texto bruto, registrar
normalizações tipográficas conservadoras e verificar os resultados novamente
contra a fonte. Não usar segmentação por quantidade de caracteres nem
`lastRenderedPageBreak` para inventar páginas originais. Sem prova de páginas,
com conteúdo visual não extraído ou dúvidas textuais, exigir revisão e impedir
checkpoint/categorização. Não corrigir valores, custos, regras ou hifenizações
ambíguas automaticamente. Não marcar o livro como `done`.

## Pendências conhecidas

O vínculo ao inventário histórico é candidato por nome único, sem decisão de
edição registrada. As 89 marcas de renderização do DOCX não certificam páginas
da obra original. O piloto legado não declara páginas de origem. A confirmação
de versão/páginas e a revisão de conteúdo visual são etapas posteriores.

## Ensaio

Extraídos 2.609 blocos de três partes XML (2.605 parágrafos principais, quatro
de notas), 7.196 nós de texto Word e 14 tabelas. Há 118 partes de mídia e 89
marcas de renderização. Nenhuma ligatura foi normalizada neste arquivo.
O motor parou na extração com as pendências de páginas e revisão visual, sem
checkpoint de extração, categorização ou aprovação humana automática.
Artefatos guardados fora do checkout no runtime
`/workspace/.daemon_runtime/real-extraction-corondor-20261015`.
Relatório: `docs/reports/2026-10-15-real-extraction-corondor.md`.
