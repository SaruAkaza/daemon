# Scale-Out / Acervo + Batch Orchestrator + Painel Operacional — Design Oficial

Data: 2026-09-14
Status: design arquitetural aprovado em seis seções; consolidação documental para revisão humana.
Origem: transição da fase Pilot/Frontend MVP (Animalidade baseline) para a fase de Scale-Out do acervo (281 livros).

## Objetivo e limites

Este documento estabelece o design arquitetural oficial para a fase de Scale-Out do Daemon Tools, estruturando a expansão do processamento do acervo de 1 livro piloto para múltiplos livros (281 livros catalogados), integrando:
1. Catálogo e projeção do Acervo completo no frontend restrito;
2. Batch Orchestrator local com controle estrito de concorrência, checkpoints e retries;
3. Fila Central de Revisão Humana (Human Review Queue) com persistência imutável de decisões;
4. Ops Controller local-first com autenticação por token efêmero e barreira fail-closed total para modo público;
5. Painel Operacional no frontend para supervisão e comandos auditáveis em tempo real via SSE.

Princípio norteador inegociável:
> **“Escalar volume sem reduzir governança.”**

Este documento é estritamente de design arquitetural e especificação técnica. Sua criação e registro não iniciam plano de implementação, geração de código, migração de banco/dados, execução de pipelines em lote ou deploy. A aprovação desta Spec é puramente documental e não autoriza publicação de conteúdo protegido.

As regras de proveniência estrita, não invenção, ontologia Relations V2, governança de direitos autorais e validação determinística de gates continuam 100% vigentes e vinculantes.

---

## 1. Arquitetura e Responsabilidades

A arquitetura do Daemon Tools na fase de Scale-Out adota o padrão de **núcleo de orquestração local com camada operacional fina**, garantindo desacoplamento total entre apresentação, transporte, autoridade de ciclo de vida e transformação de dados.

```text
+-------------------------------------------------------------------------+
|                                Frontend                                 |
|          (Visualização, Navegação, Intenção Humana e Operações)         |
+--------------------+-------------------------------+--------------------+
                     | Comandos HTTP                 ^ Eventos SSE
                     v (POST /api/ops/commands)      | (GET /api/ops/events)
+-------------------------------------------------------------------------+
|                             Ops Controller                              |
|         (Transporte Fino, Autenticação, Validação e Auditoria)          |
+--------------------+----------------------------------------------------+
                     | Despacho de Comandos Auditados
                     v
+-------------------------------------------------------------------------+
|                           Batch Orchestrator                            |
|        (Autoridade Operacional, Concorrência, Grafo e Transições)       |
+---------+--------------------------+--------------------------+---------+
          |                          |                          |
          v                          v                          v
+-------------------+      +-------------------+      +-------------------+
|  Fila Priorizada  |      |   Human Review    |      | Stores Duráveis   |
|   (Deterministic  |      |       Queue       |      | (JobStore, State, |
|      Scheduler)   |      |  (Store/Decisions)|      |  Audit, Checkpts) |
+---------+---------+      +-------------------+      +-------------------+
          | Alocação de Slots (maxActiveBooks = 3..5)
          v
+-------------------------------------------------------------------------+
|                           Pipeline por Livro                            |
|             (Extraction -> Editorial -> Entities -> Relations)         |
|                       + Projeção + QA Gates                             |
+-------------------------------------------------------------------------+
```

### 1.1 Fronteiras e Papéis

- **Frontend (`docs/assets/app.js` e views operacionais)**:
  - Responsabilidade: visualização do acervo, apresentação do estado dos livros/jobs, navegação e captura de intenções do operador humano.
  - Limite: não executa lógica de orquestração, não processa arquivos brutos e não emite transformações sem passar pelo Ops Controller.
- **Ops Controller (`scripts/ops/` / runtime local)**:
  - Responsabilidade: camada fina de transporte HTTP/SSE, autenticação via loopback/token efêmero, validação de payload sintático e registro imutável no log de auditoria.
  - Limite: não contém regras de negócio de domínio RPG, não decide elegibilidade de livros e não executa transformações do pipeline.
- **Batch Orchestrator (`scripts/orchestrator/`)**:
  - Responsabilidade: autoridade operacional máxima sobre o ciclo de vida. Gerencia a fila priorizada, impõe o teto de concorrência ativa (`maxActiveBooks`), despacha jobs para os pipelines de livros, gerencia checkpoints, aplica regras de invalidação por DAG e descarrega livros em bloqueio ou revisão.
  - Limite: não é um servidor HTTP, não manipula diretamente sockets de rede e opera como máquina de estados determinística orientada a eventos e comandos.
- **Pipeline por Livro (`scripts/agents/` / subagentes de estágio)**:
  - Responsabilidade: execução estrita das etapas de transformação do livro (`Extraction`, `Editorial`, `Entities`, `Relations`), geração de projeção e validação fail-closed via QA Gates.
  - Limite: não tem visão global dos demais livros, não disputa recursos diretamente e atende exclusivamente às ordens de despacho emitidas pelo Orchestrator.
- **Stores Duráveis (`runtime/stores/` / JSON em disco)**:
  - Responsabilidade: persistência atômica e durável de jobs (`JobStore`), revisões humanas (`ReviewStore`), decisões (`DecisionLog`), auditoria de comandos (`CommandAuditLog`) e checkpoints de estágio.
  - Limite: armazenamento desacoplado do ciclo de vida dos processos; o estado persistido nos arquivos é a fonte única da verdade (Single Source of Truth).
- **Humano (Operador / Revisor)**:
  - Responsabilidade: autoridade final sobre ambiguidades de domínio, políticas de direitos autorais e aprovação terminativa de conclusão (`DONE`).
  - Limite: interage exclusivamente através de decisões auditadas e ações controladas registradas formalmente.

### 1.2 Decisões de Engenharia

1. **Núcleo de orquestração + camada operacional fina**: O motor de execução e a máquina de estados não dependem de HTTP nem de frameworks web, viabilizando execução headless, CLI ou migração futura para CI/servidor sem reescrever o núcleo.
2. **Ops Controller isento de lógica de domínio**: O Ops Controller limita-se a autenticar, validar contratos de transporte e repassar comandos ao Orchestrator.
3. **Batch Orchestrator desacoplado de rede**: O Orchestrator não escuta portas de rede diretamente; sua interface é puramente programática e orientada a transições e stores.
4. **Persistência durável em disco**: Todo o estado da orquestração reside em arquivos JSON duráveis, sincronizados com garantias de atomicidade de escrita local (write-temp-and-rename).
5. **SSE apenas como transporte de eventos**: Server-Sent Events é estritamente um mecanismo de notificação push em tempo real para atualização da interface. Nunca é fonte da verdade. A fonte da verdade reside exclusivamente nos stores duráveis em disco.
6. **Local-first com retomada determinística (Crash Recovery)**: Qualquer queda de energia, encerramento de processo ou reinicialização permite retomar o processamento a partir do último checkpoint consolidado sem reprocessar etapas íntegras.
7. **Evolutividade para CI/servidor**: A segregação formal de responsabilidades garante que, no futuro, a execução do pipeline possa ocorrer em runners distribuídos ou pipelines de CI mantendo exatamente o mesmo contrato de APIs e UI.

---

## 2. Acervo, Status e Fila Priorizada

### 2.1 Visibilidade Completa e Independência de Estados

O Acervo do Daemon Tools registra **281 livros** que devem ser apresentados de imediato no catálogo restrito, independentemente de já terem sido processados pelo pipeline técnico.
- **Livro cadastrado não significa processado.**
- **Livro processado não significa publicável.**

Para garantir governança absoluta, cada livro no Acervo é caracterizado por dois eixos de estado rigorosamente ortogonais e independentes:

#### Eixo 1: Ciclo de Vida do Pipeline (Operacional)
1. `WAITING`: cadastrado no acervo, aguardando elegibilidade ou disponibilidade de slot de execução.
2. `RUNNING`: estágio em execução ativa por um subagente sob controle do Batch Orchestrator.
3. `BLOCKED`: processamento suspenso devido a falha técnica determinística, dependência não resolvida ou bloqueio externo.
4. `NEEDS_HUMAN_REVIEW`: execução pausada aguardando avaliação e resolução humana na Human Review Queue (ex.: ambiguidade editorial ou semântica).
5. `READY_FOR_HUMAN_APPROVAL`: todos os estágios do pipeline e gates de QA concluídos com sucesso; aguardando homologação humana final.
6. `DONE`: homologação humana concluída e formalmente registrada; livro finalizado no acervo.
7. `FAILED`: falha não recuperável que encerrou o job após esgotamento de retries autorizados.

#### Eixo 2: Governança de Publicação (Direitos Autorais)
- `rightsStatus`: metadado legal canônico (`UNKNOWN`, `PUBLIC_DOMAIN`, `PROPRIETARY`, `AUTHORIZED`).
- `publicationMode`: modo de exposição autorizado (`NOT_PUBLIC`, `RESTRICTED_PREVIEW`, `PUBLIC`).

> **Regra de Governança Inegociável:**
> `DONE + NOT_PUBLIC` é um estado perfeitamente válido, comum e seguro. Um livro pode atingir 100% de processamento e validação de regras com sucesso técnico completo, permanecendo estritamente restrito por razões de direitos autorais (`NOT_PUBLIC`). O avanço técnico jamais força ou presume publicação externa.

### 2.2 Páginas Individuais de Livro e Projeção Operacional

- **Página individual (`#/book/:bookId`)**: Todo livro possui uma rota dedicada, mesmo que tenha 0 entidades processadas.
- **Conteúdo da página de livro**:
  - Stepper visual dos estágios do pipeline (`Source` -> `Extraction` -> `Editorial` -> `Entities` -> `Relations` -> `QA`).
  - Status atual do pipeline, status de publicação e prioridade na fila.
  - Metadados do acervo (título, cenário, ano, linha editorial, ISBN quando houver).
  - Entidades, relações e estatísticas catalogadas (exibindo `0` quando o livro ainda não foi processado).
- **Natureza do Acervo**: O Acervo é uma **projeção operacional derivada**, não uma nova fonte de dados canônica. Ele consolida metadados de catálogo e status dos stores duráveis para consumo da UI, sem alterar as fontes primárias (`Livros/` e `data/entities/`).

### 2.3 Fila Priorizada Determinística e Critérios de Escalonamento

A fila de execução é regida por um escalonador determinístico baseado em pesos explícitos, versionados, testáveis e imutáveis durante a execução:

```text
Score = W_input * Score_input + W_complexity * Score_complexity + W_dep * Score_dep + W_priority * Score_priority
```

- **Critérios de pontuação**:
  1. *Disponibilidade de insumos brutos* (`Score_input`): presença de DOCX estruturado limpo ou OCR certificado.
  2. *Complexidade e volume* (`Score_complexity`): número estimado de páginas e densidade de tabelas/regras.
  3. *Grafo de dependências entre livros* (`Score_dep`): livros de regras básicas/cenário central antecedem expansões e suplementos dependentes.
  4. *Prioridade operacional humana* (`Score_priority`): peso adicional atribuído manualmente por operador.
- **Estados de elegibilidade na fila**:
  - `REGISTERED`: livro existente no acervo, mas com insumos brutos ausentes ou incompletos (não elegível para execução imediata).
  - `QUEUED`: livro elegível com insumos certificados, aguardando vaga no pool ativo segundo seu score determinístico.
  - `INELIGIBLE`: livro explicitamente marcado como suspenso, sem autorização de processamento ou dependente de pré-requisito faltante.
- **Override manual seguro**: O operador humano pode ajustar a prioridade de um livro na fila (`PrioritizeBook`), alterando sua ordem de entrada no pool ativo, mas **o override jamais pula gates de QA, não burla checagens de integridade e não força execução sem insumos certificados**.

---

## 3. Human Review Queue + Ops API + Segurança

### 3.1 Human Review Queue (Fila Central de Revisão Humana)

Ambiguidade de domínio, divergência de regras e questões de política de direitos jamais são decididas probabilisticamente por agentes. Elas geram itens formais na Human Review Queue.

#### Estrutura do Review Record:
```json
{
  "reviewId": "REV-20260914-TREVAS-001",
  "bookId": "trevas-3ed",
  "stage": "EDITORIAL",
  "reason": "Conflito de custo de atributo entre tabela da p. 45 e texto da p. 48",
  "severity": "HIGH",
  "evidence": {
    "file": "data/extracted/trevas-3ed/editorial.json",
    "excerptA": "Tabela: Custo 3 pts por nível",
    "excerptB": "Texto corrido: Custo de 2 pontos por graduação",
    "sourcePages": [45, 48]
  },
  "agentRecommendation": "Adotar regra da tabela por precedência padrão Daemon, anotando ressalva de errata",
  "impact": "Altera cálculo de 12 fichas de NPC e 4 perícias derivadas",
  "createdAt": "2026-09-14T14:32:00Z",
  "status": "PENDING"
}
```

#### Ações Humanas Disponíveis:
- **Aprovar (`ApproveReview`)**: aceita a recomendação do agente ou confirma o dado com resolução explícita.
- **Rejeitar (`RejectReview`)**: rejeita o artefato proposto, invalidando o estágio e exigindo reformulação.
- **Pedir Correção (`RequestCorrection`)**: envia apontamentos detalhados de volta ao estágio com instruções específicas.

Todas as decisões humanas geram um registro imutável no `DecisionLog` contendo: `decisionId`, `reviewId`, `bookId`, `decidedBy` (identificador do operador), `decision`, `justification`, `timestamp` e `sha256` do artefato revisado. O Batch Orchestrator consome este log para destravar ou invalidar o estágio correspondente.

### 3.2 Ops API Local (`POST /api/ops/commands`)

Todas as mutações operacionais passam obrigatoriamente por um único endpoint assíncrono e transacional:

```http
POST /api/ops/commands
Content-Type: application/json
Authorization: Bearer <ephemeral-local-token>

{
  "commandId": "CMD-f81d4fae-7dec-11d0-a765-00a0c91e6bf6",
  "command": "PrioritizeBook",
  "bookId": "demonio-guia",
  "payload": {
    "priorityWeight": 150
  },
  "reason": "Priorização para teste da linha demônios solicitada pelo coordenador"
}
```

#### Ciclo de Vida do Comando Assíncrono:
```text
[Submissão] -> ACCEPTED (202 Accepted, retorna commandId)
                     |
                     v
                 RUNNING (Orchestrator processa em background)
                     |
         +-----------+-----------+
         |                       |
         v                       v
     SUCCEEDED                FAILED / BLOCKED
```

### 3.3 Segurança e Isolamento

1. **Loopback Only**: O Ops Controller vincula-se estritamente à interface loopback (`127.0.0.1` e `::1`). Qualquer requisição recebida em interface pública ou externa é recusada na camada de rede.
2. **Token Efêmero por Sessão**:
   - Gerado criptograficamente com alta entropia (`secrets.token_urlsafe(32)`) na inicialização do serviço local.
   - Gravado exclusivamente em arquivo transitório de runtime (`.daemon_runtime/ops_token`), com permissões restritas de sistema de arquivos (chmod 600).
   - **O token efêmero nunca entra no Git** (`.gitignore` explícito e verificado).
3. **Validação de Origem e Headers**:
   - `Host`, `Origin` e `Referer` validados contra `127.0.0.1:<port>` e `localhost:<port>`.
   - `Content-Type` obrigatoriamente exigido como `application/json`.
4. **Idempotência Forte de Comandos**:
   - Todo comando carrega um `commandId` (UUID v4 ou similar).
   - Reenvios com o mesmo `commandId` retornam imediatamente o status do comando original, garantindo que nenhuma ação seja executada duas vezes.
5. **Fail-Closed no Modo Público**:
   - No modo público (`mode=public` / GitHub Pages / distribuição estática), o Ops Controller sequer é instanciado.
   - Nenhuma rota `/api/ops/*` existe em modo público. Tentativas de requisição recebem `404 Not Found` fail-closed.

### 3.4 Confirmação Proporcional ao Risco

A interface de usuário e o Ops Controller exigem rituais de confirmação proporcionais ao impacto operacional da ação:

| Nível de Risco | Ações | Ritual de Confirmação |
| :--- | :--- | :--- |
| **Baixo** | Priorizar livro na fila, Pausar orquestrador, Retomar orquestrador | Clique de confirmação simples em modal ou botão toggle. |
| **Médio** | Reprocessar estágio individual, Rejeitar item de review, Pedir correção com instrução | Confirmação detalhada com preview dos estágios impactados e motivo obrigatório. |
| **Alto** | Alteração de `rightsStatus`, alteração de `publicationMode`, invalidação ampla de múltiplos estágios/livros, remoção definitiva de checkpoints, autorização de publicação | Confirmação forte: digitação explícita do identificador do livro/ação, preenchimento de justificativa auditável obrigatória e verificação de duplo consentimento. Não é permitida automação não assistida para ações de alto risco. |

### 3.5 Atualizações em Tempo Real via Server-Sent Events (SSE)

Para manter a interface em sincronia imediata sem polling agressivo:
- **Endpoint**: `GET /api/ops/events` (loopback autenticado via token).
- **Mecanismo**: SSE padrão (MIME `text/event-stream`), emitindo eventos estruturados com `id`, `event` e `data` em formato JSON.
- **Replay Limitado**: Suporte a reconexão utilizando o header `Last-Event-ID`, reenviando eventos de um buffer circular recente (ex.: últimos 100 eventos).
- **Eventos Conceituais**:
  - `job.updated`: alteração de status de um livro/estágio (ex.: transição de `WAITING` para `RUNNING`).
  - `queue.changed`: reordenação de prioridades, inclusão ou remoção de livros na fila.
  - `review.created`: novo item gerado para a Human Review Queue.
  - `review.resolved`: item de revisão humana solucionado.
  - `command.updated`: progresso de comando assíncrono (`ACCEPTED` -> `RUNNING` -> `SUCCEEDED`/`FAILED`).
  - `stage.invalidated`: notificação de invalidação em cascata de estágios por alteração upstream.
- **Garantia de Não-Autoridade do SSE**: Se a conexão SSE for interrompida ou falhar, o frontend realiza fallback automático consultando os stores persistidos via polling seguro. O SSE é puro transporte de notificação; **os stores duráveis são a autoridade absoluta**.

---

## 4. Batch, Checkpoints, Retries e Invalidação

### 4.1 Fila Contínua e Capacidade Concorrente

O Batch Orchestrator processa múltiplos livros em paralelo sob parâmetros rígidos de concorrência:
- **Capacidade inicial (`maxActiveBooks`)**: **3 livros simultâneos**.
- **Elevação para 5 livros**: permitida somente após demonstração empírica de estabilidade em testes e ondas controladas de rollout.
- **Isolamento de falhas e bloqueios**:
  - O bloqueio ou ida para revisão de um livro (ex.: Livro B entra em `NEEDS_HUMAN_REVIEW`) **não paralisa nem afeta os outros livros ativos**.
  - Um livro bloqueado ou aguardando revisão é imediatamente **descarregado do pool ativo**, liberando seu slot de concorrência.
  - A próxima vaga no pool é preenchida automaticamente pelo próximo livro elegível de maior prioridade na fila (`QUEUED`).

### 4.2 Checkpoints Granulares por Estágio Concluído

O pipeline é estritamente transacional e particionado por estágio:
- **Princípio do Checkpoint**: um checkpoint só é gravado **após a conclusão e aprovação integral do estágio em seu respectivo QA Gate**.
- **Nunca retomar do meio de uma transformação**: se um estágio for interrompido abruptamente (crash, desligamento, timeout), ele é descartado e reexecutado desde o início daquele estágio na retomada.
- **Metadados obrigatórios do Checkpoint**:
  ```json
  {
    "stage": "ENTITIES",
    "status": "PASSED",
    "inputHash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "outputHash": "sha256:4a53c4d114c00a6c230620245a49c4f74d084c8f2c3bf95a5f7d3a01a30489ef",
    "contractVersion": "relations-v2",
    "attempt": 1,
    "startedAt": "2026-09-14T15:00:10Z",
    "completedAt": "2026-09-14T15:02:45Z",
    "artifactReferences": [
      "data/entities/character_option/poder.json",
      "data/entities/relations.json"
    ],
    "handoffReferences": [
      "handoffs/trevas-3ed/entities-to-relations.md"
    ],
    "warnings": []
  }
  ```

### 4.3 Retomada Determinística (Crash Recovery)

Ao reiniciar o Orchestrator após uma parada não planejada:
1. Carrega todos os stores duráveis (`JobStore`, `ReviewStore`, checkpoints).
2. Reconstrói o grafo de dependências e a fila priorizada.
3. Valida a integridade dos artefatos em disco contra os `outputHash` registrados nos checkpoints.
4. Preserva integralmente todos os estágios válidos cujos hashes coincidam.
5. Reagenda para execução exclusivamente o estágio que estava em andamento no momento da parada (`RUNNING` -> reexecução limpa).

### 4.4 Taxonomia de Falhas e Política de Retries

O Orchestrator estabelece um teto estrito de **máximo de 2 retries além da tentativa inicial** (total de até 3 tentativas), classificando as falhas em 4 categorias formais:

```text
                               +-----------------------------+
                               |     Falha no Pipeline       |
                               +--------------+--------------+
                                              |
               +------------------------------+------------------------------+
               |                              |                              |
               v                              v                              v
    [TRANSIENT_TECHNICAL]         [DETERMINISTIC_TECHNICAL]       [DOMAIN_AMBIGUITY /
    - Lock temporário de I/O      - Violação de Schema JSON        POLICY_OR_RIGHTS]
    - Timeout de subprocesso      - Erro de sintaxe em parser     - Conflito editorial
    - Instabilidade de filesystem - ID de entidade inválido       - Dúvida de direitos
               |                              |                              |
               v                              v                              v
       Retry Automático               Bloqueio Imediato             Human Review Queue
      (Backoff Exponencial;           (Sem retry inútil;            (Livro -> NEEDS_HUMAN_REVIEW;
         máximo 2 retries)             Livro -> BLOCKED)             descarrega slot do pool)
```

- **`TRANSIENT_TECHNICAL`**: Falha puramente sistêmica e passageira (ex.: timeout transitório, arquivo momentaneamente bloqueado pelo OS). **Somente esta categoria recebe retry automático**, com backoff exponencial (ex.: 2s, 8s).
- **`DETERMINISTIC_TECHNICAL`**: Erro que se repetirá invariavelmente se o código e os inputs forem idênticos (ex.: quebra de validação de schema JSON Draft 2020-12, payload malformado). **Não recebe retry automático**. Transiciona imediatamente para `BLOCKED` com emissão de alerta técnico.
- **`DOMAIN_AMBIGUITY`**: Dúvidas semânticas, regras contraditórias no livro original ou lacunas de texto. Não recebe retry automático; gera registro na Human Review Queue e move o livro para `NEEDS_HUMAN_REVIEW`.
- **`POLICY_OR_RIGHTS`**: Questões relativas a licença, autorização ou dúvidas de propriedade intelectual. Move imediatamente o livro para `BLOCKED` sob governança de direitos.

### 4.5 Invalidação por Grafo de Dependências (DAG Upstream/Downstream)

O pipeline interno de cada livro segue um grafo direcionado acíclico estrito:

```text
Source -> Extraction -> Editorial -> Entities -> Relations -> Frontend -> QA
```

- **Regra de Invalidação**: Se um estágio intermediário for alterado (por exemplo, edição corretiva em `Editorial` ou novo insumo em `Source`), o Orchestrator **invalida deterministicamente apenas o estágio alterado e todos os seus descendentes downstream**.
  - Exemplo: alteração em `Entities` invalida `Entities`, `Relations`, `Frontend` e `QA`. Os estágios `Source`, `Extraction` e `Editorial` permanecem com seus checkpoints íntegros e não são reexecutados.
- **Transição para `DONE`**: Um livro só transiciona para o estado terminal `DONE` após satisfazer cumulativamente:
  1. Conclusão com sucesso de todos os estágios do pipeline e aprovação em todos os QA Gates;
  2. Alcance do estado preliminar `READY_FOR_HUMAN_APPROVAL`;
  3. Registro formal e criptográfico de homologação humana no `DecisionLog`.

---

## 5. Acervo e Painel Operacional no Frontend

### 5.1 Arquitetura de Navegação Restrita

No ambiente restrito (`mode=restricted`), a navegação do Daemon Tools é estruturada em dois macro-ambientes:

```text
+-------------------------------------------------------------------------+
|                       Daemon Tools — Modo Restrito                      |
+------------------------------------+------------------------------------+
|             Consulta               |             Operações              |
|  - Início                          |  - Visão Geral Operacional (#/ops) |
|  - Acervo (#/books)                |  - Fila Priorizada (#/ops/queue)   |
|  - Entidades (#/entities)          |  - Human Review Queue (#/ops/revs) |
|  - Busca (#/search)                |  - Jobs Ativos (#/ops/jobs)        |
+------------------------------------+------------------------------------+
```

> **Barreira de Modo Público:**
> Em modo público (`mode=public`), toda a seção de **Operações (`#/ops/*`) é eliminada**. Os links de menu não são renderizados, as rotas não são registradas no router do frontend e qualquer tentativa de acesso manual à hash `#/ops` é redirecionada silenciosamente para `#/`.

### 5.2 Rotas Conceituais da Fase de Scale-Out

| Rota | Ambiente | Finalidade |
| :--- | :--- | :--- |
| `#/books` | Consulta | Catálogo completo dos 281 livros do Acervo, com filtros e cards operacionais. |
| `#/book/:bookId` | Consulta | Página individual de um livro específico (stepper de estágios, status e dados). |
| `#/ops` | Operações | Dashboard operacional consolidado com contadores e status global do sistema. |
| `#/ops/queue` | Operações | Visualização da fila priorizada, scores determinísticos e controle de concorrência. |
| `#/ops/reviews` | Operações | Fila central de revisões humanas pendentes e resolvidas. |
| `#/ops/review/:reviewId` | Operações | Detalhe de uma revisão humana, evidências comparativas e formulário de decisão. |

### 5.3 Catálogo do Acervo (`#/books`)

- **Exibição dos 281 Livros**: Todos os livros cadastrados no manifesto do acervo aparecem em formato de cards responsivos.
- **Informações do Card do Livro**:
  - Título do livro e cenário/linha editorial (ex.: Trevas, Arkanun, Invasão, Anime, etc.).
  - Badge de status de Pipeline (`WAITING`, `RUNNING`, `BLOCKED`, `NEEDS_HUMAN_REVIEW`, `READY_FOR_HUMAN_APPROVAL`, `DONE`, `FAILED`).
  - Badge de Política de Publicação (`NOT_PUBLIC`, `RESTRICTED_PREVIEW`, `PUBLIC`).
  - Estágio atual do pipeline (`Source`, `Extraction`, `Editorial`, `Entities`, `Relations`, `Frontend`, `QA`).
  - Total de entidades extraídas (exibe `0` para livros não processados).
  - Score e posição na fila de processamento.
- **Filtros e Controles**:
  - Filtrar por status de pipeline, modo de publicação, linha editorial e faixa de prioridade.
  - Ordenar por prioridade na fila, título alfabético, data de cadastro ou volume de entidades.

### 5.4 Painel Operacional (`#/ops`) e Ações Controladas

- **Contadores Globais em Tempo Real**:
  - `Total Catalogado`: 281 livros.
  - `Ativos (Running)`: 0 a 3 (ou 5).
  - `Aguardando (Queued/Waiting)`: n livros.
  - `Revisões Pendentes (Needs Human Review)`: n livros.
  - `Bloqueados (Blocked/Failed)`: n livros.
  - `Prontos para Aprovação (Ready for Approval)`: n livros.
  - `Concluídos (Done)`: n livros.
- **Ações Operacionais Controladas**:
  - *Priorizar*: envia comando assíncrono para reordenar a fila determinística.
  - *Pausar / Retomar*: suspende ou retoma a ingestão de novos jobs pelo Orchestrator.
  - *Reprocessar Estágio*: invalida e reexecuta um estágio a partir de seu checkpoint.
  - *Aprovar / Rejeitar / Pedir Correção de Review*: resolve itens da Human Review Queue.
- **Regra de Integridade Absoluta**: Nenhuma ação no Painel Operacional edita arquivos de dados (`data/entities/`, `relations.json`) de forma arbitrária ou manual. Todas as mutações derivam de reexecuções válidas dos estágios do pipeline sob os QA Gates formais.
- **Feedback Assíncrono e Otimista**: Ao disparar um comando, a interface reflete imediatamente o estado `ACCEPTED` com indicador de carregamento, atualizando-se de forma definitiva assim que o evento SSE (`command.updated` / `job.updated`) for recebido do Ops Controller.

---

## 6. Segurança, Testes, Rollout e Aceite

### 6.1 Matriz de Comportamento Fail-Closed

O sistema protege-se contra estados inválidos adotando comportamento fechado para falhas em todas as camadas:

```text
Cenário / Requisição                          Comportamento Fail-Closed
-------------------------------------------   ----------------------------------------------------
Token ausente ou inválido                     HTTP 401 Unauthorized; comando descartado.
Origem externa ou não-loopback                Conexão recusada / HTTP 403 Forbidden.
commandId repetido                            HTTP 200/202 com replay do status original (idempotente).
Transição de estado inválida                  HTTP 409 Conflict; estado da máquina permanece inalterado.
bookId inexistente no acervo                  HTTP 404 Not Found; nenhum job ou lock é criado.
Qualquer rota /api/ops/* em modo público      HTTP 404 Not Found; rotas nem sequer existem no router.
Inconsistência em checkpoint de stage         Checkpoint ignorado; força reexecução limpa do estágio.
Ambiguidade de regra não resolvida            Livro não avança; move para NEEDS_HUMAN_REVIEW.
```

### 6.2 Auditoria Completa de Comandos (`CommandAuditLog`)

Cada ação enviada ao Ops Controller é persistida em log imutável (`runtime/stores/command_audit.jsonl`):
- `commandId`: identificador único do comando.
- `commandType`: nome da operação solicitada.
- `bookId` / `reviewId`: alvo do comando.
- `previousState`: estado do alvo antes da aplicação.
- `actionPayload`: parâmetros fornecidos.
- `reason`: justificativa fornecida pelo operador (obrigatória para médio e alto risco).
- `result`: status final (`SUCCEEDED`, `FAILED`, `REJECTED`).
- `timestamp`: carimbo ISO 8601 UTC.
- `decisionId`: vínculo com a decisão humana, quando aplicável.

### 6.3 Estratégia de Testes Automatizados por Camada

1. **Acervo**:
   - Teste de renderização e projeção dos 281 registros de catálogo.
   - Testes de filtragem, busca e ordenação no catálogo.
   - Teste de integridade de página de livro para itens com 0 entidades.
2. **Batch Orchestrator**:
   - Testes unitários do escalonador determinístico de fila.
   - Teste de concorrência estrita: verificação de que jobs ativos nunca ultrapassam `maxActiveBooks`.
   - Testes de descarregamento de slot quando livro transiciona para `BLOCKED` ou `NEEDS_HUMAN_REVIEW`.
   - Testes de crash recovery: reinicialização simulada com checkpoints parciais e integridade de hashes.
3. **Human Review Queue**:
   - Teste de ciclo de vida completo do review (`PENDING` -> `APPROVED`/`REJECTED`).
   - Teste de assinatura e persistência no `DecisionLog`.
   - Teste de bloqueio de transição para `DONE` sem homologação humana formal.
4. **Ops Controller & Segurança**:
   - Testes de rejeição de chamadas com token inválido, expirado ou forjado.
   - Testes de contenção de rede: rejeição de IPs que não sejam loopback.
   - Testes de idempotência de comandos assíncronos.
   - Teste de isolamento público: garantia de ausência total de endpoints operacionais em modo público.
5. **Server-Sent Events (SSE)**:
   - Teste de emissão e serialização de eventos conceituais.
   - Teste de reconexão e replay ordenado utilizando `Last-Event-ID`.
6. **Frontend**:
   - Testes de componentes (Jest/DOM) para cards do acervo, steppers e modais operacionais.
   - Testes automatizados de navegador (Playwright): navegação por rotas restritas `#/ops/*` e verificação de bloqueio em modo público.

### 6.4 Teste E2E Sintético Concorrente (Cenário de 5 Livros)

Para validação completa da suíte de orquestração antes do uso em livros reais, é obrigatória a execução de um teste ponta a ponta com **5 livros sintéticos simultâneos**, projetados para exercitar todos os ramos do sistema:

- **Livro A (Caminho Feliz)**: executa todos os estágios sem erros técnicos ou ambiguidades -> atinge `READY_FOR_HUMAN_APPROVAL` -> recebe homologação humana simulada -> atinge `DONE`.
- **Livro B (Ambiguidade Editorial)**: atinge estágio `Editorial` com conflito de texto injetado -> transiciona para `NEEDS_HUMAN_REVIEW` -> é descarregado do pool ativo -> aguarda resolução humana sem travar os outros livros.
- **Livro C (Falha Técnica Transitória)**: sofre timeout simulado de I/O na tentativa 1 -> Orchestrator classifica como `TRANSIENT_TECHNICAL` -> aplica retry 1 com backoff -> conclui com sucesso na tentativa 2.
- **Livro D (Fila e Capacidade)**: com capacidade máxima fixada em 3 livros (Livros A, B e C ocupando slots), Livro D permanece em `QUEUED` -> assim que Livro B é descarregado para review, Livro D assume o slot vago imediatamente.
- **Livro E (Invalidação em Cascata DAG)**: sofre modificação sintética de arquivo de entrada no estágio `Entities` -> Orchestrator invalida `Entities`, `Relations`, `Frontend` e `QA`, preservando `Source`, `Extraction` e `Editorial` íntegros.

#### Evidências Obrigatórias Coletadas no E2E Sintético:
- Em nenhum instante a concorrência ativa excedeu 3 livros simultâneos.
- O bloqueio do Livro B não afetou nem atrasou o processamento dos Livros A, C e D.
- O retry do Livro C foi contido e respeitou a contagem máxima.
- A invalidação do Livro E não regrediu estágios anteriores independentes.
- Um restart simulado do processo durante a execução do Livro D recuperou o estado íntegro dos checkpoints em disco.

### 6.5 Rollout Gradual em Ondas (Waves)

A expansão do processamento real do acervo é escalonada em ondas sucessivas de validação:

- **Wave 0 (Baseline)**:
  - Livro *Animalidade* utilizado como baseline ouro e referência de conformidade.
- **Wave 1 (Lote Controlado Pequeno)**:
  - 3 livros reais de baixa complexidade processados em concorrência `maxActiveBooks = 3`.
  - Validação de checkpoints, geração de reviews e performance dos stores.
- **Wave 2 (Lote de Complexidade Mista)**:
  - 3 livros adicionais contendo cenários com dependências de regras e tabelas complexas.
  - Teste de estresse dos rituais de decisão humana e resolução de pendências.
- **Wave 3 (Expansão de Concorrência)**:
  - 5 livros simultâneos processados após cumprimento integral dos critérios de elevação.
- **Fila Contínua (Full Scale-Out)**:
  - Ativação do processamento contínuo sobre os 281 livros do acervo, com reabastecimento automático do pool ativo.

#### Critérios Formais para Elevar Concorrência de 3 para 5 Livros:
1. Zero corrupção ou inconsistência detectada nos stores persistidos;
2. Zero vazamento de dados restritos para diretórios públicos ou logs não controlados;
3. Zero colisão de arquivos temporários ou condições de corrida entre jobs simultâneos;
4. Zero perda de progresso após interrupções de processo com checkpoints ativos;
5. Retries automáticos comportando-se de forma previsível e estritamente limitados a <= 2;
6. Fila de revisão humana isolando ambiguidades de domínio com clareza de evidências;
7. Invalidação em cascata demonstrando precisão milimétrica em testes reais;
8. Volume de revisões humanas geradas dentro de limites sustentáveis pelo operador humano.

### 6.6 Estratégia de Entregas Incrementais (Releases)

Para viabilizar entrega contínua com risco reduzido, a implementação poderá ser fatiada em três releases autônomos:

- **Release A — Acervo 281**:
  - Expansão do catálogo para 281 livros visíveis no frontend restrito.
  - Projeção de metadados de catálogo, cards informativos e páginas individuais `#/book/:bookId`.
  - Filtros e ordenações no Acervo.
- **Release B — Painel Operacional + Ops Controller + Review Queue**:
  - Implementação da camada fina do Ops Controller local com autenticação por token efêmero.
  - Implementação da Human Review Queue e persistência de decisões no `DecisionLog`.
  - Rotas operacionais `#/ops/*` no frontend com contadores e comandos auditados.
- **Release C — Batch Orchestrator Contínuo**:
  - Implementação do motor de concorrência ativa (3 a 5 livros) e fila priorizada determinística.
  - Checkpoints automáticos por estágio, taxonomia de retries e invalidação em cascata por DAG.
  - Execução contínua de lote com preenchimento automático de vagas.

---

## 7. Critérios de Aceite da Fase

A fase de Scale-Out será considerada concluída com sucesso quando todos os seguintes critérios forem comprovados:

1. **281 livros catalogados e navegáveis**: todos os livros do acervo são visíveis no Acervo restrito com status claro de pipeline e publicação.
2. **Concorrência segura e controlada**: Batch Orchestrator executa 3 a 5 livros em paralelo sem condições de corrida ou contenção de recursos.
3. **Fila priorizada contínua**: escalonamento determinístico que descarrega livros bloqueados e aloca novas vagas automaticamente.
4. **Resiliência e Checkpoints**: retenção de checkpoints íntegros por estágio e recuperação limpa de falhas via crash recovery.
5. **Retries técnicos controlados**: máximo de 2 retries automáticos estritamente para falhas transitórias.
6. **Centralização de Revisão Humana**: Human Review Queue operando com captura completa de evidências e persistência imutável de decisões.
7. **Comandos auditáveis**: Ops Controller local registrando 100% dos comandos em log append-only com justificativas auditáveis.
8. **Atualizações em tempo real**: SSE mantendo a interface sincronizada sem substituir os stores duráveis.
9. **Invalidação precisa por DAG**: alterações upstream invalidam estritamente o estágio modificado e seus dependentes downstream.
10. **Homologação humana obrigatória para `DONE`**: nenhum livro atinge `DONE` sem homologação humana formal registrada.
11. **Fail-closed total em modo público**: zero endpoints `/api/ops/*`, zero menus operacionais e zero vazamento de conteúdo restrito.
12. **Princípio fundamental respeitado**: volume do acervo expandido com preservação integral de todas as barreiras de governança e rigor técnico.
