# Corondor — auditoria privada de extração

Responsável: Codex. Branch: `codex/real-extraction-review-adapters`.
Estado do livro: `needs_review`, 2026-10-15; o livro não foi aprovado.
Continuação na mesma branch: pacote HTML privado entregue no runtime,
navegável e independente de servidor para conferir texto, mídia e páginas.
As anotações exportadas serão rascunhos vinculados aos hashes da fonte/evidência;
não serão decisões humanas canônicas nem removerão gates automaticamente.

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

## Conferência posterior pelo usuário

Caderno privado em `review/corondor-revisao-20261015.html` dentro do runtime,
12.334.794 bytes. Preserva os 2.609 blocos; 118 prévias verificadas no Chromium,
126 vínculos aos parágrafos e nenhuma mídia sem vínculo recuperado. Inclui
busca, filtro e exportação/importação de notas `DRAFT_UNVERIFIED` ligadas aos
hashes da fonte/evidência e dos itens. Sem salvamento automático ou aplicação
canônica. Leia `docs/reference/real-extraction.md` antes de usar/exportar notas.
Nenhuma aprovação humana registrada; paginação e revisão visual seguem abertas.
