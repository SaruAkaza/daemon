# Biblioteca pessoal Daemon

Entrada do produto: **anexar → extrair/OCR → buscar e ler**. Aplicação estática
em JavaScript, com PDF.js, Tesseract português/inglês e IndexedDB. Os arquivos e
o texto permanecem no navegador; nenhum endpoint recebe os livros anexados.

```bash
cd web/library
npm ci
npm test
npm run build
python -m http.server 8080 --bind 127.0.0.1 --directory dist
```

Abra `http://127.0.0.1:8080`. O HTTPS da hospedagem ou localhost é necessário
para os recursos de segurança do navegador. A instalação e o build são tarefas
de desenvolvimento; o usuário da instância publicada só seleciona arquivos.

O build aceita uma saída absoluta: `node build.mjs /caminho/privado/dist`.
É gerado um diretório estático independente, com engines, workers, fontes,
modelos de OCR e licenças servidos pela mesma origem. Dependências têm versões
fixas e lockfile; `node_modules/` e `dist/` não são versionados. O CI instala,
constrói e executa os testes de modelo, cópia e navegador, incluindo OCR real.

## Escopo da conversão

- PDF: texto nativo e OCR automático de páginas com pouco texto; preserva páginas
  físicas e páginas vazias, e oferece visualização da página original.
- Imagens PNG/JPEG/WebP/GIF/BMP: OCR português/inglês. Várias imagens podem virar
  um livro, ordenado naturalmente pelos nomes (`2` antes de `10`). A imagem de
  origem continua disponível. GIF usa o primeiro quadro.
- DOCX: parágrafos, tabelas, cabeçalhos, rodapés, notas e texto Word fora de
  parágrafos, mantendo localizadores e páginas desconhecidas. Não renderiza a
  diagramação nem faz OCR das mídias dentro de um DOCX.
- Organização inicial por títulos explícitos, estilo, caixa e contexto de
  categoria. Trechos sem título são agrupados em limites de parágrafo.
  Normalização limitada a ligaturas Unicode; sem adivinhar custos ou regras.
- Pesquisa por texto/categoria/livro, leitura e download do original.
- Salva somente livros completos em transação; duplicatas não sobrescrevem.
  Cancelamento preserva livros já salvos e não cria um livro parcial.
- Exporta ZIP com texto convertido e originais. Restauração valida limites,
  estrutura, IDs/hashes/bytes da fonte, rejeita duplicatas internas/caminhos
  inseguros e adiciona livros sem substituir os que já existem.

## Limites e autoridade

50 MiB por arquivo; até 1.500 páginas/imagens e 100.000 blocos, 12 milhões de
caracteres por livro. DOCX tem limite de 64 MiB de XML descompactado e 4.096
partes. ZIP de cópia até 128 MiB, 100 livros/3.000 entradas e metadados de texto
até 32 MiB. Imagens são redimensionadas para OCR; podem perder texto pequeno.
O navegador também impõe sua própria quota de armazenamento/memória.

Biblioteca pessoal é `PERSONAL_UNVERIFIED`, diferente do catálogo certificado:
não cria entidades/relações canônicas, decisões humanas, checkpoints, `done` ou
permissões de publicação. Categorias são sugestões iniciais, não certificação
semântica. Word não recebe páginas inventadas. PDFs usam o contador físico,
não necessariamente o número impresso. OCR pode errar números/palavras;
o usuário pode consultar a fonte preservada sem preencher formulário técnico.
Páginas PDF com bastante texto nativo usam esse texto; esta versão não faz OCR
complementar de cada figura numa página mista. A consulta não atesta cobertura
semântica ou visual total do livro.

Os livros não sincronizam automaticamente entre dispositivos. A interface
explica que a biblioteca fica neste navegador e oferece cópia/restauração.
Não há chave de LLM, provedor remoto ou upload de conteúdo para terceiros.

## Hospedagem privada

O Site privado existente pode servir `dist/` sem backend. Preserve seu
`.openai/hosting.json` e audiência; não copie obras para o GitHub público.
Um livro já existente no projeto pode ser oferecido opcionalmente por uma
configuração **apenas da instância privada**:

```json
{"starter":{"path":"private/arquivo.docx","name":"arquivo.docx"}}
```

Esse objeto fica em `dist/library-config.json` e exibe um botão de importação;
o download/conversão só ocorre ao clicar. O build padrão não inclui obra alguma.
Nenhum worker recebe conexões externas ou executa conteúdo HTML da fonte.
Não transforme o Site em público para distribuir material de direitos desconhecidos.
