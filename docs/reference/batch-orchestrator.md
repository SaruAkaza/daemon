# Motor privado de lotes — Release C

A Release C executa uma fila persistente com até três livros simultâneos,
checkpoints após validação de cada etapa e retomada no limite da etapa. Está
implementada e exercitada com fontes sintéticas. Os seis executores do acervo
real ainda precisam de integração e certificação; o motor não fornece um
extrator semântico ou serviço LLM pronto. A migração dos pilotos continua pendente.

A factory de [extração real e preparação de revisão](real-extraction.md) já
conecta PDF/DOCX e a preparação editorial. Ela bloqueia quando faltam páginas,
revisão visual ou classificação; as etapas semânticas posteriores não simulam
sucesso. O ensaio real não certificou livros nem concluiu a migração.

## Demonstração executável

Requer Python 3.12, dependências do projeto e Linux/POSIX (`flock`). Na raiz:

```bash
python -m scripts.orchestrator --demo --runtime-dir /tmp/daemon-demo
python -m scripts.orchestrator --demo --runtime-dir /tmp/daemon-demo --serve --port 8080
```

O primeiro comando encerra quando os cinco livros saem da fila ativa. O segundo
mantém o painel em `http://127.0.0.1:8080/?site=1#/ops`. A autenticação local e os controles
de risco do preview continuam ativos. A identificação do operador é uma declaração
local, não autenticação corporativa. Use runtime novo para repetir o ensaio do zero.

A e E chegam à revisão final; B registra ambiguidade editorial; C bloqueia por
falha determinística; D sofre uma falha transitória e retoma. Nenhum recebe
aprovação humana automática. O teste de recuperação de D mata um processo real;
o teste de E reprocessa entidades e confere a preservação de fonte, extração e
editorial. Os artefatos de demonstração são identificados como sintéticos.

## Integração com executores reais

```bash
python -m scripts.orchestrator \
  --runtime-dir /caminho/privado/daemon-runtime \
  --source-root /caminho/do/checkout \
  --registry /caminho/privado/lote.json \
  --adapters meu_modulo:build_executors --serve
```

O registro privado é uma lista de objetos `bookId`, `manifest` (o objeto completo
do schema existente `source-manifest`) e `metadata` opcional. Um livro sem
manifesto fica `REGISTERED`; `metadata.suspended=true` o torna `INELIGIBLE`.
`manifest.path` é relativo a `source-root`; no acervo real começa por `Livros/`.
Não há inscrição automática dos 269 DOCXs nem promoção dos vínculos candidatos.

A factory confiável retorna um `StageExecutor` para cada etapa: `extraction`,
`editorial`, `entities`, `relations`, `frontend`, `qa`. Cada contrato declara
versão e schemas existentes. `run(context)` escreve no diretório exclusivo
da tentativa e retorna `{caminhoRelativo: nomeDoSchema}`. `validate(context,
payloads)` é o gate independente: aceita retornando `None` e rejeita levantando
uma exceção. Deve verificar limpeza/certificação, proveniência, páginas,
cobertura e regras da etapa. JSON válido sozinho não prova qualidade editorial.
Os adaptadores são código local confiável, não plugins isolados em sandbox;
devem usar timeouts nos serviços externos. O motor não mata uma thread travada.

`context.predecessors` contém os checkpoints validados anteriores. A fonte é
verificada contra seu SHA-256 original e nunca reescrita. Sem gate independente,
contrato ou artefatos válidos a etapa bloqueia. Uma alteração no código do
adaptador/gate exige aumentar sua versão para invalidar checkpoints antigos.

## Persistência, falhas e controle

- O runtime fica fora do checkout. Contém `jobs/`, `ops/stores/` e
  `batch/{state.json,checkpoints/,attempts/}`. Uma lease do sistema operacional
  impede dois motores no mesmo runtime e é liberada após um processo morto.
  O servidor e o motor precisam compartilhar a mesma instância de `ReviewStore`.
  Quando conectado ao motor, o preview usa esse runtime exato para os stores e
  o token; não reutiliza outro `.daemon_runtime` encontrado em um diretório pai.
- Cada tentativa usa um diretório UUID. Checkpoints guardam fonte, input,
  artefatos, hashes, schemas/versões transitivos, epoch, tentativa e timestamps.
  Arquivos, schemas e gates são novamente verificados antes da retomada.
- `TRANSIENT_TECHNICAL` tem duas retentativas, após 2 e 8 segundos. A espera
  libera a vaga. Outras falhas não têm retry automático: falhas determinísticas
  bloqueiam; ambiguidades e questões de direitos vão para revisão humana.
  Direitos desconhecidos permitem trabalho privado, nunca publicação automática.
- Uma interrupção descarta a tentativa incompleta e preserva os checkpoints
  válidos. A contagem de tentativas sobrevive ao reinício; após três tentativas
  interrompidas ou fracassadas é necessária uma correção/reexecução explícita.
- Pausa e retirada da fila concluem a etapa atual antes de liberar a vaga.
  Reprocessamento invalida apenas a etapa escolhida e suas sucessoras; resultados
  atrasados da execução anterior não podem certificar a revisão nova. A thread
  anterior continua ocupando sua vaga até terminar.
- IDs de comandos impedem reprocessamento duplicado após restart. Os controles
  de pausa, retomada, prioridade, reprocessamento e retirada do painel operam
  sobre o motor quando ele está conectado. Sem motor, permanece o registro de
  intenções da Release B. Reprocessar permite reinscrever um livro retirado.
- Aprovar uma revisão de ambiguidade/direitos registra a decisão, mas não
  inventa a correção nem muda o manifesto. Corrija a entrada/adaptador e solicite
  `REPROCESS_STAGE`. Esses livros ficam fora da fila até a ação explícita.
- Corrupção do estado, jobs ou histórico humano interrompe o motor. Não é
  corrigida por exclusão silenciosa. O painel apresenta o erro do motor.

## Aprovação e publicação

Após QA, o livro fica `READY_FOR_HUMAN_APPROVAL`. A decisão humana precisa citar
o `snapshotSha256` apresentado na revisão; o histórico imutável guarda o hash,
o livro, a etapa e o tipo de revisão. Um reprocessamento muda o snapshot e torna
a decisão anterior insuficiente para aprovar o resultado novo.

A aprovação técnica produz **`APPROVED_PRIVATE`**, com job canônico `approved`.
O estágio canônico `release` permanece `waiting`; `done` exige todos os gates
existentes, inclusive publicação, e validação humana. Essa escolha preserva o
contrato de `GateEngine` e substitui o `DONE` técnico simplificado do plano de
Release C. O motor não escreve em `data/`, `Livros/` ou assets públicos.

Aumentar de três para quatro/cinco vagas exige revisão `BATCH_WAVE` com as oito
evidências de estabilidade do plano e aprovação humana vinculada ao hash dessas
evidências. Nada eleva a concorrência automaticamente. As ondas com livros reais
continuam pendentes até a certificação dos adaptadores e decisões de proveniência.

## Verificação

```bash
python -m pytest tests/orchestrator tests/ops tests/agents/test_preview_server_ops_barrier.py -q
node --test tests/frontend/*.test.mjs
ruff check scripts/
```

Os testes abrangem concorrência real, pausa, retry com deadline durável, kill e
restart, mudança de contrato/fonte, artefato corrompido, invalidação em cascata,
comandos repetidos e aprovação humana do snapshot. Nenhum ensaio certifica os
resultados dos livros reais ou concede direitos de publicação.
