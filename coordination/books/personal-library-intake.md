# Entrada de livros e biblioteca pessoal — Codex

Estado de implementação: `needs_review`, 2026-10-15; sem aprovação humana final.
Branch: `codex/book-upload-library`, sobre PR #4.

O usuário reafirmou o objetivo: anexar PDF/imagens/DOCX e consultar o conteúdo
convertido na ferramenta. Esta entrega substitui o caderno técnico como entrada
principal do Site privado existente, preservando sua audiência de proprietário.

Escopo: conversão no navegador, OCR português/inglês de imagens/PDFs escaneados,
busca, organização inicial por títulos e categorias explícitas, leitura da fonte,
armazenamento local e cópia exportável/importável. Corondor continua atribuído
ao Codex; nenhuma outra fila/obra será reivindicada ou alterada.

Conteúdo extraído é uma biblioteca pessoal em consulta, sem certificação
semântica, entidades canônicas, inferência de regras/custos, alteração de schemas,
direitos ou `done`. PDF mantém índice físico, imagem mantém índice do arquivo;
DOCX mantém localizador estrutural e páginas desconhecidas. Não fabricar páginas.
Erros de OCR e categorias incertas ficam identificados junto ao resultado;
não exigir que o usuário classifique milhares de blocos para conseguir consultar.

Arquivos anexados e resultados permanecem neste navegador; a interface deve
explicar como exportar uma cópia. Nenhum livro real, texto integral, pacote
privado ou credencial entra no GitHub público. Testes usam fontes sintéticas.
Fonte original, acervo canônico, dados publicados e gates do motor preservados.

## Evidência de uso

PDF digital, Word, imagens em sequência e PDF escaneado passaram pela seleção
real de arquivos no Chromium; OCR português/inglês sem mock. Cancelamento,
duplicatas, busca, fonte visual, persistência e cópia/restauração em outro
contexto foram conferidos. Corondor preservou os 2.609 blocos da auditoria
anterior, com organização inicial em 66 seções. Não atribuiu páginas ao Word.

Novo fluxo em `web/library/`; relatório em
`docs/reports/2026-10-15-personal-library.md`. O Site privado existente passa a
abrir a biblioteca; o caderno anterior é preservado como arquivo auxiliar.
