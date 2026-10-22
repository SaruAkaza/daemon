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

## Caderno privado para conferir depois

O comando abaixo gera um HTML independente de servidor, com busca, navegação
em lotes de 40 blocos, texto bruto, normalizações/tokens auxiliares, prévias de
mídia DOCX e campos de anotações. Ele exige o hash da evidência baixada na
revisão e recalcula a extração contra a fonte; alterar um resultado e fornecer
seu novo hash não torna o conteúdo válido.

```bash
python -m scripts.orchestrator.review_packet \
  --source-root /caminho/do/checkout \
  --manifest /caminho/do/checkout/data/source-manifests/file-SHA256.json \
  --evidence /caminho/privado/execution-result.json \
  --evidence-sha256 HASH_DA_EVIDENCIA_NA_REVISAO \
  --output /caminho/privado/revisao.html
```

Abra o HTML no navegador, identifique a referência e escolha a numeração:
contador físico do PDF, número impresso ou página do Word na formatação atual.
O total de páginas é opcional e não atribui páginas aos trechos. Cada bloco
permite página/intervalo, observação e marca de conferência. As imagens têm
localizadores de mídia, hashes e links aos parágrafos recuperados.

**Exportar anotações** baixa um JSON de rascunho. Para continuar em outra sessão,
reabra o mesmo HTML e use **Importar anotações**. Não há salvamento automático;
o navegador avisa ao fechar com alterações não exportadas. A importação exige
os mesmos hashes de fonte/evidência, localizadores e hashes de cada item,
rejeita duplicatas e preserva o trabalho atual se o JSON for inválido. A troca
de um rascunho com mudanças locais exige confirmação na própria tela.

As anotações têm `status=DRAFT_UNVERIFIED`: não são decisões assinadas de
operador, não são importadas para stores e não removem gates. Sua conferência
será a evidência para uma etapa posterior de revisão registrada. Não há botão
de aprovação do livro neste caderno.

O arquivo contém texto e imagens privados: a saída deve ficar fora do checkout,
é criada com permissão `0600` e não sobrescreve arquivos existentes. HTML/JS/CSS
são locais; a política de conteúdo bloqueia conexões de rede e conteúdo ativo
de fontes. As prévias DOCX são pixels raster decodificados, limitados a 1.200
pixels por lado, apenas primeiro quadro, com recompressão JPEG quando aplicável.
Não preservam diagramação, resolução integral, animação ou objetos incorporados:
confira os detalhes no original. SVG/formatos não suportados ficam como
pendências sem incorporar binários ativos. Links externos nunca são acessados.
Para PDFs, o caderno mantém os blocos/páginas físicas do relatório; não renderiza
páginas nem recupera sua mídia nesta versão. Consulte o PDF para revisão visual.

Limites adicionais: 64 MiB de mídia descompactada, 2.048 partes de mídia,
20 milhões de pixels por imagem, 100 milhões no total, 16 MiB de relações DOCX
e 2 MiB por parte de relações; HTML final até 50 MiB e anotações até 10 MiB.

Limites: fonte/resultado de até 50 MiB, XML descompactado de até 64 MiB, até
100.000 blocos e 10.000 páginas PDF. Fontes inválidas bloqueiam por erro técnico.
Não há integração com provedor LLM nem certificado de edição/paginação implícito.
