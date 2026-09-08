# Daemon Tools — Version 2.2 Design Specification
# Pilot Content Pipeline (End-to-End Book Verification)

## 1. Visão Geral e Contexto

Esta especificação define a arquitetura, contratos de dados, máquina de estados, governança de direitos autorais, protocolo de auditoria e fluxo de execução da **Version 2.2 — Pilot Content Pipeline** do repositório Daemon Tools.

O objetivo central da Versão 2.2 é fechar o ciclo operacional completo de transformação de dados processando **um livro real** desde sua fonte original não estruturada até sua visualização navegável, pesquisável e com relações ativas em ambiente de preview local, exercitando todas as camadas do pipeline:
```text
Fonte Original (Livros/)
  ↓
SOURCE (Inventário, integridade, direitos)
  ↓
EXTRACTION (Texto bruto, limpeza, parágrafos)
  ↓
EDITORIAL (Segmentação, classificação, cobertura de páginas)
  ↓
ENTITIES (Extração e tipagem canônica de entidades)
  ↓
RELATIONS (Grafos de regras, vínculos e referências cruzadas)
  ↓
VALIDATION (Validação técnica determinística de schemas e contratos)
  ↓
LEGACY COMPARISON (Comparação determinística sem LLM contra histórico)
  ↓
PILOT HUMAN REVIEW (Solicitação formal vs Decisão humana hash-bound)
  ↓
V2.1 PERSISTENCE (Mutação atômica segura via ApplicationCoordinator em data/)
  ↓
QA / RELEASE GATES (Validação determinística de conformidade e integridade)
  ↓
LOCAL PREVIEW PROJECTION (Projeção runtime-only isolada em <runtime>/preview/)
  ↓
LOCAL HTTP PREVIEW (Navegação, busca e relações ativas via runtime overlay)
```

---

## 2. V2.1 Baseline e Cláusulas Pétreas

A Versão 2.2 tem como alicerce estrito a **Version 2.1 — Persistence/Application Layer**, congelada e verificada na tag:
- **Tag:** `multiagent-persistence-v2.1`
- **SHA:** `d4622b3cdee956f5cb8dfff34df0a98e3e4dfe13`

Todas as garantias e invariantes de segurança da V2.1 permanecem vigentes e inalteradas:
1. **Zero Mutação Fora da V2.1:** Toda e qualquer escrita de dados no repositório passa obrigatoriamente pelo `ApplicationCoordinator` / `ChangeSetApplier` da V2.1. O pipeline piloto e seus agentes não possuem autoridade de escrita direta no repositório.
2. **ACCEPT Boundary Inviolável:** O construtor de alterações (`ChangeSetBuilder`) e o coordenador de aplicação exigem deterministamente que o veredicto de validação técnica seja `ACCEPT`.
3. **Interseção Estrita de Autoridade:** $\text{Scope} = \text{allowedWriteScope} \cap \text{AutoApplyRoots} \cap \text{ApplicationPolicy}$. O request jamais pode expandir raízes de aplicação.
4. **Proteção TOCTOU e Primitivas Atômicas:** Revalidação de estado em disco na Fase 4 pré-mutação, criação atômica exclusiva (`open(..., "xb")` / `O_EXCL`), substituição unitária no mesmo volume (`os.replace`) e journal de rollback compensatório com detecção de adulteração concorrente.
5. **Isolamento de Staging e Bundles:** Os pacotes operacionais e áreas de staging residem fora da árvore Git, no mesmo sistema de arquivos do repositório (`<repo-parent>/.daemon_runtime/`).

---

## 3. Goals e Non-Goals

### 3.1 Goals (Metas da Versão 2.2)
1. **Processar 1 Livro Real:** Executar a cadeia completa de extração, estruturação, catalogação e integração de uma obra a partir de sua fonte original em `Livros/word/`.
2. **Exercitar Todos os Estágios do Pipeline:** SOURCE, EXTRACTION, EDITORIAL, ENTITIES, RELATIONS, VALIDATION, QA e LOCAL PREVIEW.
3. **Operacionalizar a Ponte de Transporte Manual com Antigravity:** Implementar o protocolo estruturado de exportação de `ExecutionBundle` e importação de `ResultBundle` para operação assistida por humano, sem automações frágeis.
4. **Vínculo Criptográfico Bidirecional de Bundles:** Garantir que o pacote de resposta esteja amarrado por hashes imutáveis (`requestId`, `executionBundleId`, `inputManifestSha256`, `artifactHashes`) ao pacote de entrada.
5. **Validador de Integridade de Importação:** Estabelecer a fronteira `BundleIntegrityValidator` para barrar dados corrompidos, incompletos ou adulterados antes de qualquer avaliação de regras de negócio.
6. **Comparador Determinístico com Legado (`LegacyComparator`):** Contrastar estruturalmente o resultado do pipeline com referências derivadas antigas para alertar o operador humano sobre divergências mecânicas, sem uso de LLM e sem conferir autoridade ao legado.
7. **Separação Formal entre Review Request e Review Decision:** Registrar a solicitação de revisão e vincular criptograficamente a decisão humana de aprovação ao hash SHA-256 exato do manifesto do resultado revisado.
8. **Auditoria de Governança Confiável e Segregada (`PilotAuditStore`):** Persistir evidências de governança em armazenamento durável controlado pelo runtime confiável, fora do repositório e totalmente inacessível a auto-apply de ChangeSets de conteúdo.
9. **Projeção de Preview Runtime-Only (`LocalPreviewProjector`):** Para obras com direitos restritos ou desconhecidos (`NOT_PUBLIC`), projetar dados de preview exclusivamente em diretório de runtime não rastreado (`<runtime>/preview/<bookId>/`), servido por overlay local sem tocar a árvore `docs/`.
10. **Integração Mínima com o Frontend Existente:** Permitir navegação, filtragem, busca e visualização de relações no visualizador local (`localhost`), sem refatorações de framework.
11. **Testabilidade Hermética:** 100% dos novos componentes testáveis offline em fixtures isoladas, sem tokens, segredos ou chamadas externas.

### 3.2 Non-Goals (Fora do Escopo da Versão 2.2)
1. **Deploy ou Publicação em Produção:** Proibida a publicação automática ou manual de conteúdo restrito no GitHub Pages público.
2. **Materialização de Conteúdo Restrito em `docs/`:** Dados derivados de fontes `NOT_PUBLIC` ou `UNKNOWN` jamais entram na árvore rastreada pelo Git (`docs/assets/data/`). Repositórios e branches públicas não são ambientes privados.
3. **Automação de API com Antigravity / Gemini:** A integração programática de rede permanece classificada como `DEFERRED_PENDING_RUNTIME_API`.
4. **Automação de Interface ou Navegador:** Proibido o uso de Selenium, Playwright, Puppeteer, PyAutoGUI ou similares.
5. **Assinaturas Digitais PKI:** A integridade é garantida por hashes SHA-256 canônicos e amarração de manifestos; infraestrutura de certificados assimétricos é postergada.
6. **Reconciliação Semântica Automática:** O `LegacyComparator` não interpreta significados nem usa IA. Divergências semânticas exigem deliberação humana.
7. **Redesign do Frontend ou Migração de Stack:** Nenhuma reescrita em React, Vue, Svelte ou Next.js. Proibida a introdução de novos design systems ou bibliotecas pesadas de UI.
8. **Processamento em Lote Multi-Livro ou Swarm:** Apenas 1 livro piloto será processado em sequência controlada.

---

## 4. Critérios de Sucesso do Piloto (`V2.2 VERIFIED`)

A Versão 2.2 só atinge o estado `V2.2 VERIFIED` quando os seguintes critérios objetivos forem atendidos:

1. **Fonte Real Processada:** 1 livro selecionado deterministicamente a partir de seu arquivo original em `Livros/`.
2. **Cadeia Completa Concluída:** Dados transformados através de todos os estágios formais do pipeline.
3. **Ponte Manual Operada com Sucesso:** Exportação de bundles pelo Daemon, inferência assistida pelo Antigravity/Gemini e importação sem falhas de formato.
4. **Integridade de Bundle Validada:** `BundleIntegrityValidator` aprova a amarração de identidade, hashes de manifestos e ausência de adulteração.
5. **Divergências Semânticas Auditadas:** O `LegacyComparator` classifica todas as alterações e direciona diferenças para aprovação humana.
6. **Aprovação Humana Registrada no `PilotAuditStore`:** Decisão formal de revisão emitida e vinculada criptograficamente ao manifesto do resultado, fora da autoridade do modelo.
7. **Persistência Exclusiva via V2.1:** Arquivos gravados no repositório estritamente através do `ApplicationCoordinator` da V2.1 em `data/`, com journals limpos e sem violações TOCTOU.
8. **QA Automatizado Verde:** Suíte de testes (`pytest`), `validate_data.py`, `check_book_coverage.py` e sintaxe JS aprovados com exit code 0.
9. **Navegabilidade Comprovada no Preview Local:** O livro piloto aparece no visualizador local servido via runtime overlay, com listagem de seções e entidades.
10. **Busca Funcional no Preview Local:** Termos e entidades do livro piloto retornam nos filtros e busca do frontend local.
11. **Relações Clicáveis no Preview Local:** Links cruzados entre entidades navegam corretamente na interface local.
12. **Bloqueio Absoluto de Publicação Pública:** Comprovado que nenhum arquivo derivado de `animalidade` foi adicionado a `docs/` ou exposto a deploy público.

---

## 5. Seleção Determinística do Livro Piloto e Evidência Canônica de Direitos

### 5.1 Critérios Determinísticos de Avaliação da Shortlist
A seleção obedece a 6 dimensões determinísticas auditáveis:
- **C1. Disponibilidade de Fonte Original:** Arquivo DOCX íntegro em `Livros/word/`.
- **C2. Existência de Dados Legados:** Presença prévia em `data/books/` e `data/pilot/`.
- **C3. Qualidade da Fonte:** Documento com `badLineScore == 0.0` no relatório de qualidade (`word-docx-quality-report.json`).
- **C4. Extensão Gerenciável:** Entre 10 e 50 páginas (permite ciclo ágil de transporte manual sem cansaço operacional).
- **C5. Representatividade do Domínio Daemon:** Variedade de classes de entidades (mínimo 4 áreas: Lore, Regras, Opções/Poderes, NPCs).
- **C6. Governança de Direitos Canônicos:** Status de direitos auditado com base em evidência documental, sem inferências implícitas.

### 5.2 Shortlist Auditada e Evidência Canônica de Direitos

Em conformidade com a Constituição do Projeto (Seção 8):
> **Regra de Ouro de Direitos:** `UNKNOWN` nunca deve virar permissão implícita. Na ausência de documento formal de liberação assinado pelos detentores dos direitos ou comprovação de domínio público, o status canônico padrão é estritamente `rightsStatus = UNKNOWN` e o modo de publicação é `publicationMode = NOT_PUBLIC`.

| Livro Candidato | Págs. | Chars | Áreas Representadas | Registro Canônico | rightsStatus | publicationMode | eligible_for_local_pilot | eligible_for_public_release |
|:---|:---:|:---:|:---|:---|:---:|:---:|:---:|:---:|
| **1. animalidade** | 13 | 58.659 | Lore, Regras, Rituais, Poderes, Aprimoramentos, Raças, NPCs | `data/index/sources.json` (`Livros/animalidade.pdf`, `Livros/word/animalidade.docx`) | `UNKNOWN` | `NOT_PUBLIC` | **SIM** | **NÃO** |
| **2. alastores-a-justica-infernal** | 43 | 88.518 | Lore, Poderes, Aprimoramentos, Classes, Itens, Rituais, NPCs | `data/index/sources.json` (`Livros/Alastores - A Justiça Infernal.pdf`) | `UNKNOWN` | `NOT_PUBLIC` | **SIM** | **NÃO** |
| **3. anoes** | 8 | 37.190 | Aprimoramentos, Lore, Itens, Kits, Raças | `data/index/sources.json` (`Livros/anoes.pdf`) | `UNKNOWN` | `NOT_PUBLIC` | **SIM** | **NÃO** |
| **4. anjos-cacadores-alados** | 43 | 116.108 | Lore, Raças, Manobras, Aprimoramentos, Poderes, NPCs | `data/index/sources.json` (`Livros/Anjos cacadores-alados.pdf`) | `UNKNOWN` | `NOT_PUBLIC` | **SIM** | **NÃO** |

### 5.3 Decisão de Seleção: `animalidade`
O suplemento **`animalidade`** é designado como o piloto da V2.2 sob as seguintes restrições explícitas de governança:
- **PILOT MODE:** `LOCAL_RESTRICTED`
- **PUBLIC DEPLOYMENT:** `BLOCKED`
- **Evidência Documental:** Registrado em `data/index/sources.json` (13 páginas, DOCX limpo em `Livros/word/animalidade.docx`, `badLineScore: 0.0`, zero tabelas truncadas).
- **Justificativa Técnica:** Excelente representatividade de regras e lore Daemon em volume ideal (13 páginas) para validação do transporte assistido.
- **Isolamento de Direitos:** Por ter `rightsStatus = UNKNOWN` e `publicationMode = NOT_PUBLIC`, seus dados derivados residirão canonicamente em `data/` e serão projetados para preview exclusivamente em diretório runtime-owned não rastreado (`<runtime>/preview/animalidade/`). É estritamente proibido espelhar seus dados em `docs/assets/data/`.
- **Regra de Não-Contaminação:** O pipeline começa obrigatoriamente de `Livros/word/animalidade.docx`. Os dados antigos (`data/pilot/animalidade.json`, `data/books/animalidade.json`) servem unicamente ao `LegacyComparator` como espelho comparativo de qualidade, nunca como entrada de extração.

---

## 6. Matriz Canônica de Direitos e Projeção de Preview

A autorização para visualização e publicação obedece rigorosamente à seguinte matriz de decisão determinística:

| rightsStatus | publicationMode | Local Preview Proj. (`LocalPreviewProjector`) | Public Proj. (`PublishProjector`) | Destino Autorizado |
|:---|:---|:---:|:---:|:---|
| **`AUTHORIZED` / `PUBLIC_DOMAIN`** | `FULL_TEXT` / `SUMMARY_AND_METADATA` | **PERMITIDO** | **ELEGÍVEL** (após QA + Gates + Aprovação Humana) | Local: `<runtime>/preview/`<br>Público: `docs/assets/data/` |
| **`METADATA_ONLY`** | `METADATA_ONLY` | **PERMITIDO** (restrito a metadados) | **ELEGÍVEL** (restrito a metadados) | Local: `<runtime>/preview/`<br>Público: `docs/assets/data/` |
| **`PRIVATE`** | `NOT_PUBLIC` | **PERMITIDO** (somente desenvolvimento local) | **BLOQUEADO** | Local: `<runtime>/preview/` apenas |
| **`UNKNOWN`** | `NOT_PUBLIC` | **PERMITIDO** (somente desenvolvimento local) | **BLOQUEADO** | Local: `<runtime>/preview/` apenas |

*Qualquer tentativa de projetar conteúdo `PRIVATE`, `UNKNOWN` ou `NOT_PUBLIC` para `docs/` ou qualquer árvore Git é barrada com erro `ERR_RESTRICTED_CONTENT_PROJECTION_BLOCKED`.*

---

## 7. Arquitetura Operacional do Piloto

O desacoplamento entre a orquestração do Daemon e o ambiente externo do modelo é mediado por pacotes autocontidos e serializados em disco:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ DAEMON RUNTIME (Local Engine)                                                          │
│                                                                                        │
│   [Pilot Job Definition (Attempt N)]                                                   │
│             ↓                                                                          │
│   [ExecutionBundleExporter]                                                            │
│             ↓                                                                          │
│   (.daemon_runtime/bundles/outgoing/<bundle-id>/) ──────────────────────────┐          │
└─────────────────────────────────────────────────────────────────────────────┼──────────┘
                                                                              │
                                                                     [Manual Transport]
                                                                     (Operador Humano)
                                                                              │
┌─────────────────────────────────────────────────────────────────────────────┼──────────┐
│ EXTERNAL MODEL ENVIRONMENT                                                  │          │
│                                                                             ▼          │
│   Antigravity / Gemini Workspace ──→ (Processa Prompt e Salva Output)                  │
│                                                                             │          │
└─────────────────────────────────────────────────────────────────────────────┼──────────┘
                                                                              │
                                                                     [Manual Transport]
                                                                     (Operador Humano)
                                                                              │
┌─────────────────────────────────────────────────────────────────────────────┼──────────┐
│ DAEMON RUNTIME (Local Engine)                                               ▼          │
│                                            (.daemon_runtime/bundles/incoming/<id>/)    │
│                                                                             ↓          │
│   [ResultBundleImporter]                                                               │
│             ↓                                                                          │
│   [BundleIntegrityValidator] ──→ (Falha?) ──→ [VALIDATION_FAILED]                      │
│             ↓ (Pass)                                                                   │
│   [ExecutionResultValidator] ──→ (Não ACCEPT?) ──→ [VALIDATION_FAILED]                  │
│             ↓ (Pass)                                                                   │
│   [LegacyComparator] (Determinístico, sem LLM)                                         │
│             ↓                                                                          │
│   [PilotReviewRequest] ──→ Gravado no PilotAuditStore (<runtime>/audit/)               │
│             ↓                                                                          │
│   [PilotReviewDecision] (Humano) ──→ Gravado no PilotAuditStore (Rejeição: REJECTED)   │
│             ↓ (Aprovação hash-bound)                                                   │
│   [ApplicationCoordinator V2.1]                                                        │
│             ↓ (Mutação atômica em data/ via AutoApplyRoots)                            │
│   [Canonical Repository Data (data/)]                                                  │
│             ↓                                                                          │
│   [QA / Release Gates] ──→ (Falha?) ──→ [QA_FAILED]                                    │
│             ↓ (Pass)                                                                   │
│   [Rights Gate] ──→ (NOT_PUBLIC / UNKNOWN?) ──┐                                        │
│             ↓                                 ▼                                        │
│   [PublishProjector] (BLOCKED)     [LocalPreviewProjector]                             │
│                                               ↓                                        │
│                                    (<runtime>/preview/animalidade/)                    │
│                                               ↓                                        │
│                                    [Local HTTP Server Overlay]                         │
│                                    (Serve docs/app.js + dados runtime)                 │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Fronteiras Distintas de Projeção e Autoridade de Código

### 8.1 Separação entre `LocalPreviewProjector` e `PublishProjector`
1. **`LocalPreviewProjector` (Runtime-Only):**
   - **Autoridade:** Runtime local confiável.
   - **Gatilho:** Executado somente após QA Gates PASS e verificação de direitos.
   - **Destino:** `<repository-parent>/.daemon_runtime/preview/<bookId>/`.
   - **Comportamento:** Projeta os dados estruturados de `data/pilot/<livro>.json` e gera o índice runtime correspondente. O servidor local de teste (ex.: script Python HTTP de preview) faz o overlay entre os assets de código em `docs/` e os dados em `<runtime>/preview/`.
   - **Isolamento:** **Zero arquivos criados em `docs/` ou rastreados pelo Git.**
2. **`PublishProjector` (Publicação / Deploy):**
   - **Autoridade:** Gate de release e direitos estrito.
   - **Requisitos:** `rightsStatus` compatível (`AUTHORIZED` ou `PUBLIC_DOMAIN`) + `publicationMode` compatível + QA PASS + aprovação humana expressa de publicação.
   - **Destino:** `docs/assets/data/`.
   - **Status na V2.2:** **DESATIVADO / BLOQUEADO.** A V2.2 não realiza publicação pública de conteúdo.

### 8.2 Código do Frontend $
e$ Persistência de Conteúdo
- Ajustes em `docs/index.html` e `docs/assets/app.js` (para renderizar novos atributos, filtros ou campos de entidades) são **intervenções normais de desenvolvimento de software** realizadas pelo desenvolvedor humano na branch Git `feat/pilot-content-pipeline-v2-2`.
- O pipeline de conteúdo e a camada de persistência da V2.1 **NUNCA** têm permissão de alterar arquivos de código (`.js`, `.html`, `.css`) através de auto-apply.

---

## 9. Máquina de Estados do Piloto e Modelo de Tentativas (Rework/Attempt Model)

### 9.1 Imutabilidade Absoluta de Bundles
- **Execution Bundle Exportado é Imutável:** Uma vez gravado na pasta `outgoing/`, torna-se somente leitura. É proibido editar um bundle in-place para "corrigir um prompt".
- **Result Bundle Importado é Imutável:** Uma vez recebido em `incoming/`, o pacote não pode ser alterado.
- **Rework Gera Nova Tentativa:** Se um resultado for corrompido, reprovado na validação ou rejeitado na revisão humana, o operador cria uma nova tentativa com identificador sequencial:
  ```text
  Job: JOB-ANIM-001-EXTRACTION
  ├── attempt 1 (EB-ANIM-001-att1 / RB-ANIM-001-att1) -> FAILED / REJECTED
  ├── attempt 2 (EB-ANIM-001-att2 / RB-ANIM-001-att2) -> APPROVED / PERSISTED
  └── ...
  ```
- **Sem Retry Automático:** O sistema nunca entra em loops de retry autônomos. Cada tentativa requer geração explícita de bundle e transporte manual pelo operador.

### 9.2 Diagrama de Estados do Piloto

```mermaid
stateDiagram-v2
    [*] --> READY_TO_EXPORT
    READY_TO_EXPORT --> WAITING_FOR_RESULT: export_bundle(attempt_n)
    
    WAITING_FOR_RESULT --> RESULT_IMPORTED: import_bundle(attempt_n)
    
    RESULT_IMPORTED --> VALIDATION_FAILED: integridade / schema / contrato inválido
    VALIDATION_FAILED --> REWORK_REQUIRED: registrar motivo da falha no PilotAuditStore
    
    RESULT_IMPORTED --> NEEDS_HUMAN_REVIEW: integridade PASS & legacy comparado
    
    NEEDS_HUMAN_REVIEW --> REJECTED: decisão humana == REJECT
    REJECTED --> REWORK_REQUIRED: registrar apontamentos humanos no PilotAuditStore
    
    REWORK_REQUIRED --> READY_TO_EXPORT: criar nova tentativa (attempt_n+1)
    
    NEEDS_HUMAN_REVIEW --> APPROVED: decisão humana == APPROVE (hash-bound)
    
    APPROVED --> PERSISTED: application_coordinator.apply() (V2.1 em data/)
    APPROVED --> VALIDATION_FAILED: V2.1 policy / TOCTOU falha
    
    PERSISTED --> QA_PASS: todos os QA gates PASS
    PERSISTED --> QA_FAILED: QA gate FAIL
    QA_FAILED --> REWORK_REQUIRED: erro estrutural ou de cobertura
    
    QA_PASS --> PREVIEW_READY: local_preview_projector.project() (<runtime>/preview/)
    PREVIEW_READY --> PILOT_VALIDATED: checklist de navegação e busca validado em localhost
    PILOT_VALIDATED --> [*]
```

---

## 10. Canonicalização e Algoritmo de Hashing de Bundles

Para assegurar que bundles logicamente idênticos possuam hashes imutáveis e reprodutíveis independentemente do sistema operacional ou relógio, o cálculo de hashes obedece a um algoritmo estrito de canonicalização.

### 10.1 Algoritmo Canônico de Serialização JSON
Toda estrutura de metadados antes de ser hasheada deve ser convertida em bytes UTF-8 via:
```python
def canonical_json_bytes(payload: dict) -> bytes:
    # 1. Ordenação lexicográfica recursiva de todas as chaves
    # 2. Separadores compactos sem espaços adicionais: ',' e ':'
    # 3. Formato UTF-8 estrito sem BOM e sem escape desnecessário
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return serialized.encode("utf-8")
```

### 10.2 Separação entre Content Identity e Audit Metadata
- **`inputManifestSha256` (Content Identity Hash):** É calculado exclusivamente sobre o payload canônico de conteúdo de `context-manifest.json` contendo: `bundleId`, `requestId`, `jobId`, `stage`, `bookId` e a lista ordenada de `items` (cada um com `logicalPath`, `role`, `sourceUri`, `sizeBytes`, `sha256`, `mediaType`). O campo temporal `createdAt` é estritamente **excluído** do cálculo do hash de identidade do conteúdo.
- **`executionBundleId`:** Derivado deterministicamente como:
  `EB-<BOOK_ID>-<STAGE>-att<ATTEMPT_NUM>-<CONTENT_HASH[:8]>`.
- **`artifact hashes`:** SHA-256 calculado diretamente sobre os bytes binários brutos de cada arquivo físico presente no diretório `artifacts/`.
- **`resultManifestSha256`:** Calculado sobre a serialização canônica do conteúdo do `result-manifest.json`, excluindo eventuais campos de auto-referência circular.

---

## 11. Validador de Integridade de Importação (`BundleIntegrityValidator`)

O `BundleIntegrityValidator` atua antes de qualquer inspeção semântica. Ele impõe as seguintes validações determinísticas:

1. **Validação de Schemas:** Conformidade com `execution-result.schema.json` e `result-manifest.schema.json`.
2. **Amarração de Identidade Cruzada:**
   - `result.requestId == expected_request_id`
   - `result.executionBundleId == expected_bundle_id`
   - `result_manifest.inputManifestSha256 == expected_input_manifest_sha256`
3. **Integridade de Artefatos:**
   - Para cada arquivo no diretório `artifacts/`, calcula o SHA-256 real em disco e compara com o declarado em `result-manifest.json`. Divergência gera `ERR_ARTIFACT_HASH_MISMATCH`.
   - Se houver arquivo na pasta não declarado no manifesto: `ERR_UNEXPECTED_ARTIFACT`.
   - Se houver arquivo no manifesto ausente na pasta: `ERR_MISSING_ARTIFACT`.
4. **Hardening de Caminhos de Artefatos:** Cada caminho relativo de artefato é validado contra path traversal (`..`), drive letters, prefixos de dispositivo (`\\?\`, `\\.\`), Alternate Data Streams (`:`) e nomes reservados DOS.
5. **Limites de Recursos:** Nenhum artefato individual pode exceder 50MB e o total do bundle não pode exceder 200MB.

---

## 12. Comparador com Legado Determinístico (`LegacyComparator`)

### 12.1 Cláusula Pétrea de Determinismo (Sem LLM)
> **O `LegacyComparator` não utiliza modelos de linguagem (LLM) e não interpreta livremente o texto.** Ele opera exclusivamente através de regras de comparação determinística sobre árvores sintáticas e estruturas canônicas normalizadas.

### 12.2 Veredictos do Comparador:
1. **`SEMANTIC_EQUIVALENT`:**
   - Pode ser declarado **somente** quando a equivalência mecânica e factual puder ser comprovada deterministicamente:
     - Mesmos identificadores canônicos (`id`);
     - Mesmos tipos e categorias canônicas;
     - Mesmos valores numéricos normalizados de atributos, modificadores, custos e dados vitais;
     - Mesmas relações canônicas vinculadas;
     - Diferenças limitadas a espaçamento em branco, quebras de linha ou ordenação de campos.
   - *Ação:* Avança automaticamente.
2. **`STRUCTURAL_DIFFERENCE_ONLY`:**
   - Dados semanticamente idênticos, porém reestruturados para conformidade com novos schemas (ex.: atributos de statblock transformados de string corrida para dicionário tipado `attributes: {"FR": 15, ...}`).
   - *Ação:* Avança com registro em log de auditoria.
3. **`SEMANTIC_DIFFERENCE`:**
   - Divergências mecânicas detectadas (ex.: Força 15 vs 18; PV 25 vs 19), poderes adicionados ou omitidos, discrepância em listas de perícias ou conflito de texto descritivo.
   - *Ação:* **Bloqueio automático.** Direciona para `HUMAN_REVIEW` como ponto de deliberação no `PilotReviewRequest`.
4. **`NO_LEGACY_REFERENCE`:**
   - Entidade ou regra nova presente na fonte original que nunca constou nos extratos legados antigos.
   - *Ação:* Registrado como novo conteúdo descoberto e catalogado para revisão humana.

---

## 13. Auditoria Confiável e Segregada (`PilotAuditStore`)

### 13.1 Segregação de Autoridade do `PilotAuditStore`
Registros de governança e auditoria NÃO são dados de conteúdo derivados de livros.
- **Autoridade:** Runtime confiável local (`PilotAuditStore`).
- **Proibição Inviolável:** O motor de persistência de conteúdo da V2.1 (`ApplicationCoordinator`) e os ChangeSets gerados a partir de resultados do modelo **NÃO** possuem autoridade para criar, alterar ou assinar registros de auditoria.
- **Localização:** Os registros duráveis de governança residem em armazenamento de runtime dedicado e protegido:
  `<repository-parent>/.daemon_runtime/audit/pilot/<bookId>/`

### 13.2 Conteúdo Armazenado no `PilotAuditStore`
Para cada job e tentativa, o `PilotAuditStore` grava permanentemente:
1. `attempt-<N>-context-manifest.json`: Inventário e hashes dos insumos exportados.
2. `attempt-<N>-result-manifest.json`: Inventário e hashes dos artefatos recebidos.
3. `attempt-<N>-validation-verdict.json`: Parecer detalhado do `BundleIntegrityValidator` e `ExecutionResultValidator`.
4. `attempt-<N>-legacy-comparison.json`: Relatório estrutural emitido pelo `LegacyComparator`.
5. `attempt-<N>-review-request.json`: Solicitação formal de revisão gerada pelo sistema.
6. `attempt-<N>-review-decision.json`: Decisão formal assinada pelo operador humano, vinculada ao hash do manifesto.
7. `attempt-<N>-persistence-reference.json`: Registro de vínculo contendo `transactionId` e hash do journal da V2.1.
8. `attempt-<N>-rights-evaluation.json`: Registro formal de conformidade com a matriz de direitos.

### 13.3 Relação com os Transaction Journals da V2.1
- Os journals da V2.1 permanecem sob autoridade exclusiva da V2.1 em `audit_root` (`.daemon_audit/`).
- O `PilotAuditStore` não duplica nem substitui os journals da V2.1; apenas armazena uma referência segura (`transactionId` e SHA-256 do journal da V2.1).

### 13.4 Política de Retenção sem Perda de Governança
- A limpeza de pacotes volumosos (`outgoing/`, `incoming/`, anexos, contextos temporários, dados de preview local) **NUNCA apaga o histórico mantido no `PilotAuditStore`**.
- As evidências de identidade, hashes, pareceres de validação e decisões humanas permanecem preservadas permanentemente.

---

## 14. Governança de Revisão Humana: Separação entre Request e Decision

### 14.1 Solicitação de Revisão (`PilotReviewRequest`)
Gerada deterministicamente pelo sistema quando o `ResultBundle` é importado e validado tecnicamente. Armazenada pelo `PilotAuditStore`:
```json
{
  "$schema": "https://daemon.tools/schemas/pilot-review-request.schema.json",
  "reviewRequestId": "REV-REQ-ANIM-001-att1",
  "jobId": "JOB-ANIM-001",
  "attemptNumber": 1,
  "requestId": "req-anim-ext-001",
  "executionBundleId": "EB-ANIM-001-att1",
  "resultBundleId": "RB-ANIM-001-att1",
  "resultManifestSha256": "7c9f8e4d2a...",
  "legacyComparisonSummary": {
    "verdict": "SEMANTIC_DIFFERENCE_DETECTED",
    "equivalentCount": 14,
    "structuralDifferenceCount": 8,
    "semanticDifferenceCount": 2,
    "newEntitiesCount": 3,
    "discrepancies": [
      {
        "entityId": "feras-lobo",
        "field": "statBlock.attributes.FR",
        "legacyValue": 15,
        "extractedValue": 18,
        "sourceCitation": "Livros/word/animalidade.docx#p.11"
      }
    ]
  },
  "questionsToReviewer": [
    "Confirmar se a Força 18 do Fera Lobo é fidedigna à página 11 da fonte original."
  ],
  "status": "PENDING",
  "createdAt": "2026-09-08T18:20:00Z"
}
```

### 14.2 Decisão de Revisão (`PilotReviewDecision`)
Emitida pelo operador humano e gravada exclusivamente pelo `PilotAuditStore`. Não pode ser fabricada pelo modelo ou injetada no `ResultBundle`:
```json
{
  "$schema": "https://daemon.tools/schemas/pilot-review-decision.schema.json",
  "reviewDecisionId": "REV-DEC-ANIM-001-att1",
  "reviewRequestId": "REV-REQ-ANIM-001-att1",
  "requestId": "req-anim-ext-001",
  "executionBundleId": "EB-ANIM-001-att1",
  "resultBundleId": "RB-ANIM-001-att1",
  "reviewedResultManifestSha256": "7c9f8e4d2a...",
  "decision": "APPROVE",
  "reviewer": "operador-humano",
  "reason": "Conferido contra a pág. 11 da fonte DOCX: Força 18 é a grafia exata original; o legado antigo continha erro de digitação.",
  "decidedAt": "2026-09-08T18:30:00Z"
}
```

### 14.3 Amarração Criptográfica e Invalidação da Revisão
- O campo `reviewedResultManifestSha256` amarra a decisão humana ao conteúdo exato do pacote revisado.
- Se qualquer arquivo em `artifacts/` for modificado ou substituído após a decisão, o hash do manifesto será diferente.
- O validador detectará a divergência e invalidará a decisão imediatamente (`ERR_REVIEW_HASH_MISMATCH`), impedindo a persistência.

---

## 15. Taxonomia Canônica de Falhas

| Código Canônico | Categoria | Descrição | Ação |
|:---|:---|:---|:---|
| `ERR_EXECUTION_BUNDLE_INVALID` | Export | Estrutura de bundle de saída malformada | Aborta exportação |
| `ERR_EXECUTION_BUNDLE_INTEGRITY_FAILED` | Export | Divergência no manifesto de contexto | Aborta exportação |
| `ERR_RESULT_BUNDLE_INVALID` | Import | Schema de pacote ou manifesto inválido | `VALIDATION_FAILED` |
| `ERR_RESULT_BUNDLE_INTEGRITY_FAILED` | Import | Hash de arquivo em disco diverge do manifesto | `VALIDATION_FAILED` |
| `ERR_REQUEST_ID_MISMATCH` | Binding | RequestId retornado não bate com a saída | `VALIDATION_FAILED` |
| `ERR_BUNDLE_ID_MISMATCH` | Binding | BundleId retornado não bate com a saída | `VALIDATION_FAILED` |
| `ERR_INPUT_MANIFEST_HASH_MISMATCH` | Binding | Manifesto de entrada referenciado diverge | `VALIDATION_FAILED` |
| `ERR_ARTIFACT_HASH_MISMATCH` | Integrity | Bytes em disco divergem do hash declarado | `VALIDATION_FAILED` |
| `ERR_UNEXPECTED_ARTIFACT` | Integrity | Arquivo presente na pasta mas ausente no manifesto | `VALIDATION_FAILED` |
| `ERR_MISSING_ARTIFACT` | Integrity | Arquivo declarado no manifesto ausente na pasta | `VALIDATION_FAILED` |
| `ERR_RESULT_CONTRACT_INVALID` | Contract | Falha na validação semântica da V2 | `VALIDATION_FAILED` |
| `ERR_SEMANTIC_DIFFERENCE_REQUIRES_REVIEW` | Legacy | Divergência mecânica contra dados legados | `NEEDS_HUMAN_REVIEW` |
| `ERR_REVIEW_REQUIRED` | Review | Tentativa de persistência sem decisão registrada | Bloqueia persistência |
| `ERR_REVIEW_REJECTED` | Review | Revisor humano emitiu decisão de REJECT | `REJECTED` -> `REWORK_REQUIRED` |
| `ERR_REVIEW_HASH_MISMATCH` | Review | Artefatos adulterados após decisão humana | Invalida decisão |
| `ERR_AUDIT_STORE_VIOLATION` | Audit | Violação de integridade ou autoridade no PilotAuditStore | `VALIDATION_FAILED` |
| `ERR_PERSISTENCE_FAILED` | Persistence| Rejeição ou falha de rollback na V2.1 | `VALIDATION_FAILED` |
| `ERR_QA_FAILED` | QA | Falha em testes, schemas ou cobertura | `QA_FAILED` |
| `ERR_RESTRICTED_CONTENT_PROJECTION_BLOCKED`| Rights | Tentativa de projetar dados restritos para docs/ | Bloqueia projeção |
| `ERR_PREVIEW_PROJECTION_FAILED` | Preview | Falha ao projetar dados locais no runtime de preview | Bloqueia visualização |

---

## 16. Estratégia de Testes e CI

### 16.1 Testes Unitários e Herméticos
- `test_canonical_json.py`: Hashing determinístico, ordenação de chaves e separadores compactos.
- `test_bundle_exporter.py`: Criação de pacotes isolados, cálculo de hashes e immutability flags.
- `test_bundle_importer.py`: Leitura segura de pacotes e rejeição de adulterações.
- `test_bundle_integrity_validator.py`: Detecção de hashes divergentes, path traversal e resource bounds.
- `test_legacy_comparator.py`: Validação dos 4 veredictos sem rede e sem LLM.
- `test_pilot_audit_store.py`: Persistência segregada de governança no runtime, preservação após cleanup e proteção contra escritas via ChangeSet.
- `test_pilot_review.py`: Contratos separados de request e decision, invalidação criptográfica por hash.
- `test_preview_projector.py`: Isolamento rigoroso: dados NOT_PUBLIC projetados somente em `<runtime>/preview/`, bloqueio absoluto de escrita em `docs/`.
- `test_pilot_coordinator.py`: Máquina de estados completa, controle de tentativas (`attempt 1 -> rework -> attempt 2`) e integração V2.1.
- `test_pilot_pipeline_e2e.py`: Teste ponta a ponta hermético simulando o ciclo completo com fixtures.

### 16.2 Estratégia de CI
O GitHub Actions rodará exclusivamente os testes determinísticos e offline. Nenhum teste exigirá tokens externos, browsers reais ou credenciais de IA.

---

## 17. Componentes e Fronteiras de Arquivos Propostos

### 17.1 Schemas JSON (`schemas/`)
- `schemas/execution-bundle.schema.json`: Contrato de pacotes exportados.
- `schemas/result-bundle.schema.json`: Contrato de pacotes importados.
- `schemas/pilot-review-request.schema.json`: Contrato de solicitação formal de revisão humana.
- `schemas/pilot-review-decision.schema.json`: Contrato de decisão humana hash-bound.

### 17.2 Módulos Python (`scripts/agents/`)
- `scripts/agents/canonical_json.py`: Serialização canônica e cálculo imutável de hashes.
- `scripts/agents/bundle_exporter.py`: Exportador de Execution Bundles e manifestos de contexto.
- `scripts/agents/bundle_importer.py`: Ingestor de Result Bundles.
- `scripts/agents/bundle_integrity_validator.py`: Validador determinístico de integridade e identidade.
- `scripts/agents/legacy_comparator.py`: Comparador estrutural determinístico sem LLM.
- `scripts/agents/pilot_audit_store.py`: Armazenamento de auditoria e governança durável no runtime.
- `scripts/agents/pilot_review.py`: Gerenciador de solicitações e decisões de revisão humana.
- `scripts/agents/preview_projector.py`: Projetor isolado de preview (`LocalPreviewProjector` runtime-only).
- `scripts/agents/pilot_coordinator.py`: Orquestrador central da máquina de estados do piloto.

### 17.3 Arquivos de Teste (`tests/agents/`)
- `tests/agents/test_canonical_json.py`
- `tests/agents/test_bundle_exporter.py`
- `tests/agents/test_bundle_importer.py`
- `tests/agents/test_bundle_integrity_validator.py`
- `tests/agents/test_legacy_comparator.py`
- `tests/agents/test_pilot_audit_store.py`
- `tests/agents/test_pilot_review.py`
- `tests/agents/test_preview_projector.py`
- `tests/agents/test_pilot_coordinator.py`
- `tests/agents/test_pilot_pipeline_e2e.py`

---

## 18. Sequência de Implementação Proposta (Tasks 35–44)

- **Task 35:** Canonical JSON serializer e schemas canônicos (`execution-bundle`, `result-bundle`, `pilot-review-request`, `pilot-review-decision`).
- **Task 36:** `ExecutionBundleExporter` com amarrações de contexto e hashing canônico.
- **Task 37:** `ResultBundleImporter` e leitura segura de pacotes.
- **Task 38:** `BundleIntegrityValidator` e verificador de amarração criptográfica.
- **Task 39:** `LegacyComparator` determinístico sem LLM.
- **Task 40:** `PilotAuditStore` e `PilotReviewEngine` (segregação de auditoria durável e decisão hash-bound).
- **Task 41:** `LocalPreviewProjector` e governança de direitos para preview local runtime-only.
- **Task 42:** `PilotCoordinator` e orquestração de tentativas de retrabalho com V2.1.
- **Task 43:** Adaptações pontuais manuais de desenvolvimento no frontend (`docs/index.html`, `docs/assets/app.js`).
- **Task 44:** Teste integrado hermético E2E e execução assistida do livro piloto real (`animalidade`).

---

## 19. Self-Review de Conformidade com a Revisão 002

- [x] **Zero dados restritos em `docs/`:** Conteúdo de `animalidade` (`NOT_PUBLIC` / `UNKNOWN`) jamais é projetado para `docs/assets/data/` ou rastreado pelo Git.
- [x] **Preview local estritamente runtime-only:** O `LocalPreviewProjector` grava em `<runtime>/preview/animalidade/`, consumido via servidor HTTP local com overlay.
- [x] **Separação rigorosa entre `LocalPreviewProjector` e `PublishProjector`:** `PublishProjector` está bloqueado/desativado para fontes não autorizadas.
- [x] **Critérios de sucesso sem deploy público:** Comprovação de busca, navegação e links cruzados é realizada exclusivamente no preview local. Publicação pública permanece bloqueada.
- [x] **Auditoria de governança fora de `AutoApplyRoots`:** O `PilotAuditStore` reside em `<runtime>/audit/`, sob autoridade do runtime confiável, imune a mutações via ChangeSet de conteúdo.
- [x] **Transaction journals mantidos sob V2.1:** Não são duplicados; o `PilotAuditStore` apenas referencia seus identificadores e hashes.
- [x] **Decisão humana nasce fora do modelo:** A aprovação humana é gravada pelo `PilotAuditStore`, impossível de ser fabricada pelo executor.
- [x] **Limpeza de runtime preserva evidências:** Expurgo de pacotes brutos mantém intactos os registros duráveis no `PilotAuditStore`.
- [x] **Matriz de direitos implementada:** Mapeamento explícito de `rightsStatus` e `publicationMode` para permissões de preview e publicação.
- [x] **Status do piloto explícito:** `PILOT MODE = LOCAL_RESTRICTED`, `PUBLICATION = BLOCKED`.
