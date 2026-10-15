# Extração real e evidências privadas de revisão

`scripts.orchestrator.real_adapters:build_executors` conecta a extração de
PDF/DOCX e a preparação editorial ao motor da Release C. O executor lê uma
cópia imutável dos bytes, confere SHA-256, extrai conteúdo e produz um
`execution-result.json` no runtime privado. Não escreve no inventário,
nos pilotos, nas entidades ou nos assets públicos.

O resultado usa o schema existente `execution-result`; o contrato específico
do relatório fica em `metadata.extraction` / `metadata.editorial` e é novamente
calculado contra a fonte pelo gate. Nenhum schema global foi alterado.

## Uso

Prepare um `registry.json` privado com uma lista de `{bookId, manifest}`.
`manifest` é o objeto completo de um manifesto de fonte existente, sem alterar
direitos. No ensaio de proveniência use `bookId = manifest.sourceId`, o ID da
variante física `file-<SHA-256>`. Isso não aprova um alias ao inventário histórico.

```bash
python -m scripts.orchestrator \
  --registry /caminho/privado/registry.json \
  --adapters scripts.orchestrator.real_adapters:build_executors \
  --source-root /caminho/do/checkout \
  --runtime-dir /caminho/privado/real-extraction \
  --concurrency 1 --until-idle
```

`--until-idle` retorna um snapshot e encerra quando não há execução/retry
pendente. Código de saída zero informa que o controlador encerrou normalmente;
os estados dos livros no snapshot informam aprovação, bloqueio ou revisão.
Para usar o painel, substitua `--until-idle` por `--serve --port 8080` e abra
`http://127.0.0.1:8080/?site=1#/ops`. O runtime é externo ao checkout.

Uma retomada exige o mesmo manifesto do registro existente. Alterar o JSON
do registry não substitui uma revisão registrada: use um runtime novo ou a API
explícita `update_manifest` para uma revisão de fonte previamente conferida.

## O que é preservado

Nos DOCXs, o relatório mantém parágrafos vazios, parágrafos de tabelas,
cabeçalhos, rodapés, notas e os textos Word fora dos parágrafos. Cada bloco tem
parte XML e localizador estrutural, texto bruto, texto normalizado, hashes e
contagem das normalizações. Campos e texto de alterações excluídas ficam em
`auxiliaryTokens`; alterações rastreadas e estruturas complexas exigem revisão.
Caixas de texto aninhadas não são duplicadas nos parágrafos externos.

A normalização automática se limita às ligaturas de apresentação Unicode
U+FB00–U+FB06. Valores mecânicos, custos, suspeitas de OCR, hifens, espaçamento e
quebras são preservados. Por exemplo, `ﬁ` vira `fi`, enquanto `lO`, `1d10O` e
`ex-\nmarido` não são corrigidos por adivinhação. A auditoria de caracteres não
certifica ausência de todos os tipos de erro de OCR; a revisão editorial continua
necessária.

Nos PDFs, cada página física do arquivo é preservada, inclusive páginas vazias.
`pageBasis=PDF_PHYSICAL_INDEX` explicita o significado de `page`; números
impressos ou rótulos romanos não são deduzidos. Imagens, vetores, anotações e
widgets exigem revisão visual. O executor não faz OCR automático.

## Quando o motor para

- DOCX não comprova página da obra original. `page` e `pageCount` ficam `null`,
  com `SOURCE_PAGE_MAPPING_REQUIRED`. Quebras explícitas e marcas de última
  renderização são apenas dicas; não viram citações ou páginas certificadas.
- Conteúdo visual/embutido, alterações rastreadas, layout complexo, texto vazio
  ou caracteres suspeitos são pendências explícitas. Nenhuma dessas dúvidas
  é eliminada alterando silenciosamente o texto.
- Um PDF simples pode passar a extração técnica. O estágio editorial gera
  destinos `PENDING_CLASSIFICATION` para texto e `BLANK_PAGE` para páginas
  efetivamente vazias. Classificações pendentes exigem revisão antes de entidades.
- Os executores reais de entidades, relações, frontend e QA permanecem
  indisponíveis nesta factory e bloqueiam se chamados. Não simulam sucesso.

Uma rejeição por dúvida de domínio guarda os artefatos que já passaram por
validação de schema/hash em uma revisão ligada à tentativa, ao input, ao
contrato e aos seus hashes. A etapa rejeitada **não ganha checkpoint**.
Mudança de fonte, contrato ou bytes da evidência impede usar a revisão antiga;
reprocessamento a substitui. Aprovar uma revisão de correção não fornece páginas,
classificações ou direitos que estejam ausentes e não avança o livro sozinho.

## Acesso às evidências

A tela da revisão inclui links para baixar seus artefatos privados. O GET
`/api/ops/reviews/<reviewId>/artifact?path=<caminhoRelativo>` exige a autenticação
local do painel, usa somente referências da revisão atual e confere os hashes
antes de devolver os bytes. Conteúdo é enviado como anexo JSON com `no-store`.
O modo público retorna 404 para essa rota. O download não publica nem promove
os resultados. O modelo de identidade local do preview permanece o mesmo.

Limites: fonte/resultado de até 50 MiB, XML descompactado de até 64 MiB, até
100.000 blocos e 10.000 páginas PDF. Fontes inválidas bloqueiam por erro técnico.
Não há integração com provedor LLM nem certificado de edição/paginação implícito.
