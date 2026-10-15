# Entrada de livros e consulta pessoal — 2026-10-15

Objetivo reafirmado pelo usuário: anexar livros e converter seu conteúdo para
consulta na ferramenta. A entrega em `web/library/` coloca essa experiência na
entrada principal do Site privado existente, preservando sua audiência.
Branch `codex/book-upload-library`, sobre o PR #4.

## Comportamento entregue

Seleção/arraste de arquivos, fila sequencial, contagem automática de páginas PDF,
OCR português/inglês em imagens e PDFs escaneados, união de imagens por nome,
progresso/cancelamento e biblioteca com busca, categorias iniciais, seções e
leitura da fonte. Nenhuma página ou classificação manual é obrigatória.

PDF.js 6.4.299, Tesseract.js 7.0.0, dados de idiomas 1.0.0 e fflate 0.8.3 têm
versões fixas e lockfile. Workers/modelos/fontes são servidos pela mesma origem;
arquivos dos usuários não são enviados a um backend. IndexedDB mantém livros
completos e originais. ZIP leva a biblioteca a outro navegador; restauração
confere as fontes e preserva livros existentes.

## Ensaio de Corondor

Fonte privada já atribuída ao Codex, sem mudar seus bytes/direitos:
`Livros/word/feito/Corondor.docx`, SHA-256
`57dd236dd3e0a36888cc88f16a4d60f0121c9159c866a96475633e9fa2a98367`.

Importação executada pela tela real no Chromium. Todos os **2.609 blocos**
coincidiram com a auditoria Python anterior, incluindo parágrafos vazios,
tabelas e notas em três partes. Páginas Word permaneceram `null`. A organização
inicial produziu 66 seções: cenários 16, aprimoramentos 4, magias/rituais 10,
kits/classes 16, equipamentos 12 e poderes 8. São sugestões de navegação por
títulos/contexto, sem validar semanticamente a taxonomia do livro.

Busca e leitura verificadas em desktop 1.440 × 1.000 e celular 390 × 844, sem
erros de script ou transbordamento horizontal. Conteúdo real e screenshots
permanecem fora do GitHub público.

## Evidências técnicas

Sete testes Node do novo modelo/cópia verificam preservação de blocos/páginas
vazias, ligaturas sem alteração de valores, categorias e contexto de títulos,
busca, falsificação de formato/páginas e cópia/restauração com hashes/caminhos.
Três novos testes Chromium usam exclusivamente documentos sintéticos:

- Word e PDF digital entram pela seleção de arquivos; consulta, tabela/notas,
  duplicatas, persistência, exportação/restauração em outro contexto e download
  do original com SHA-256 igual.
- OCR real de duas imagens fora de ordem e de um PDF escaneado, categorias
  iniciais, fonte visual e apenas requisições GET da mesma origem.
- Cancelamento sem livro parcial, arquivo inválido sem impedir o próximo e
  apresentação sem transbordamento horizontal em celular.

Validação local final: **1.014 testes Python**, **46 testes Node do frontend
existente + 7 da biblioteca**, cobertura de scripts **66,80%**. Build com
dependências fixas, Ruff, dados/schemas, cobertura de livros, sincronização,
reconciliação e plano de migração aprovados. O primeiro ensaio completo expôs
uma corrida em um teste anterior de imagem lazy do caderno: a verificação agora
aguarda `image.decode()` após rolar até a imagem. A suíte completa foi repetida
e passou, mantendo a verificação de integridade da imagem.

Os arquivos exatos preparados para a publicação privada também foram servidos
localmente: o botão “Importar Corondor do projeto” fez o download/conversão e
abriu a leitura em um clique, sem erros de script. O caderno anterior foi
preservado em outra URL dentro da mesma instância privada.

## Limites preservados

Importados têm `PERSONAL_UNVERIFIED`. Não alteram acervo canônico, entidades,
relações, inventário, schemas, direitos, publicação ou decisões/checkpoints.
O motor de extração anterior continua aguardando sua certificação específica;
isso não impede a consulta pessoal do arquivo convertido.

A organização inicial não é uma catalogação semântica completa. OCR pode errar;
DOCX não tem paginação original comprovada e sua mídia interna não é reconhecida
nesta versão. Páginas mistas de PDF com bastante texto nativo usam esse texto,
sem OCR de cada figura. Armazenamento é do navegador, sem sincronização de conta;
o produto explica a necessidade de exportar para guardar/transferir.

Uso, limites de tamanho e reprodução: [biblioteca pessoal](../../web/library/README.md).
