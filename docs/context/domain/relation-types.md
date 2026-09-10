# Tipos de Relações Semânticas (Relation Types)

Este documento define o vocabulário canônico de relações semânticas e dependências de regras do **Daemon Tools**. Este vocabulário formaliza os vínculos entre entidades, permitindo a construção de grafos de regras, validação de pré-requisitos e navegação hipertextual rica.

---

## 1. Vocabulário Canônico de Relações (Ontologia V2)

### 1. `REQUIRES`
- **Significado**: A entidade de origem exige a entidade de destino como pré-requisito obrigatório para compra, escolha ou evolução.
- **Origem Esperada**: `kit_class`, `character_option`, `power_magic`, `ritual_spell`, `combat`.
- **Destino Esperado**: `attribute_skill`, `character_option`, `race_lineage`, `power_magic`, `core_rule`.
- **Exemplo**: `kit:cacador-de-bruxas` ──`REQUIRES`──> `skill:teologia`.

---

### 2. `GRANTS`
- **Significado**: A escolha da entidade de origem concede automaticamente a entidade de destino (bônus, poder, perícia ou aprimoramento gratuito).
- **Origem Esperada**: `kit_class`, `race_lineage`, `character_option`.
- **Destino Esperado**: `character_option`, `power_magic`, `attribute_skill`.
- **Exemplo**: `race:elfo` ──`GRANTS`──> `enhancement:visao-agucada`.

---

### 3. `BELONGS_TO`
- **Significado**: A entidade pertence organicamente a um agrupamento maior, caminho místico, panteão ou organização de cenário.
- **Origem Esperada**: `ritual_spell`, `creature_npc`, `item_equipment`, `kit_class`.
- **Destino Esperado**: `power_magic` (Caminho), `setting_lore` (Organização/Cenário).
- **Exemplo**: `spell:bola-de-fogo` ──`BELONGS_TO`──> `path:caminho-do-fogo`.

---

### 4. `DERIVED_FROM`
- **Significado**: A entidade é uma evolução, especialização ou variante direta de outra entidade base.
- **Origem Esperada**: `race_lineage`, `kit_class`, `power_magic`.
- **Destino Esperado**: `race_lineage`, `kit_class`, `power_magic`.
- **Exemplo**: `race:meio-elfo` ──`DERIVED_FROM`──> `race:elfo`.

---

### 5. `APPEARS_IN`
- **Significado**: A entidade é citada, reimpressa ou utilizada em múltiplos suplementos e módulos do universo.
- **Origem Esperada**: Qualquer entidade.
- **Destino Esperado**: `source`.
- **Exemplo**: `enhancement:bruto-insano` ──`APPEARS_IN`──> `source:anime-rpg-powers`.

---

### 6. `MODIFIES`
- **Significado**: A entidade ou suplemento altera, estende ou ajusta as regras ou atributos de uma entidade preexistente.
- **Origem Esperada**: `source`, `character_option`, `kit_class`, `core_rule`.
- **Destino Esperado**: `core_rule`, `attribute_skill`, `combat`, `character_option`.
- **Exemplo**: `rule:combate-avancado` ──`MODIFIES`──> `rule:iniciativa-basica`.

---

### 7. `REPLACES`
- **Significado**: A entidade ou suplemento substitui formalmente uma regra ou versão anterior em edições mais recentes.
- **Origem Esperada**: `core_rule`, `source`, `character_option`.
- **Destino Esperado**: `core_rule`, `character_option`.
- **Exemplo**: `rule:regras-daemon-3-0` ──`REPLACES`──> `rule:regras-daemon-2-x`.

---

### 8. `ALTERNATIVE_TO`
- **Significado**: A entidade representa uma variante mecânica ou opção temática equivalente a outra entidade.
- **Origem Esperada**: Qualquer entidade.
- **Destino Esperado**: Entidade da mesma categoria.
- **Exemplo**: `enhancement:imortal-centelha` ──`ALTERNATIVE_TO`──> `enhancement:imortal-classico`.

---

### 9. `HAS_POWER`
- **Definição Canônica**: the source entity actually possesses the target power.
- **Significado**: A entidade de origem efetivamente possui o poder alvo.
- **Distinção Essencial**: A posse efetiva é estritamente distinta de opções selecionáveis ou disponíveis (`actual possession != selectable/available option`).
- **Escopo**: Não adicionar restrições não declaradas na fonte, como inata, nativa, ficha padrão ou personagem inicial (do not add restrictions such as innate, native, standard stat block, or starting character). O critério de uso é a afirmação textual de que a entidade efetivamente possui o poder.
- **Origem Esperada**: `race_lineage`, `kit_class`, `creature_npc`.
- **Destino Esperado**: `power_magic`.
- **Exemplo**: `creature:vampiro-anciao` ──`HAS_POWER`──> `power:hipnose`.

---

### 10. `CAN_CHOOSE_POWER`
- **Definição Canônica**: the source entity/template is explicitly allowed to select the target power as a build or configuration option.
- **Significado**: A entidade ou template de origem tem permissão explícita para selecionar o poder alvo como uma opção de construção ou configuração.
- **Exemplos e Escopo Não Restritivo**: Exemplos de uso podem incluir criação de personagem (character creation), progressão de personagem (character progression), construção de templates (template construction), configuração de criaturas ou NPCs (creature/NPC configuration), mas esses exemplos não estreitam o significado canônico da relação.
- **Critério de Proveniência**: Utilizado quando a fonte apresenta listas de "Poderes Possíveis", menus de opções, regras de alocação de pontos de criação/compra ou tabelas de escolhas permitidas.
- **Origem Esperada**: `race_lineage`, `kit_class`, `creature_npc`.
- **Destino Esperado**: `power_magic`.
- **Exemplo**: `creature:lobisomem` ──`CAN_CHOOSE_POWER`──> `power:garras`.

---

### 11. `HAS_WEAKNESS`
- **Definição Canônica**: the source entity possesses the target weakness, vulnerability, or limitation.
- **Significado**: A entidade de origem possui a fraqueza, vulnerabilidade ou limitação alvo.
- **Origem Esperada**: `race_lineage`, `kit_class`, `creature_npc`.
- **Destino Esperado**: `character_option`.
- **Exemplo**: `creature:lobisomem` ──`HAS_WEAKNESS`──> `enhancement:vulnerabilidade-a-prata`.

---

### 12. `HAS_SKILL`
- **Significado**: A entidade possui um pacote ou requisito específico de perícias operacionais.
- **Origem Esperada**: `kit_class`, `creature_npc`.
- **Destino Esperado**: `attribute_skill`.
- **Exemplo**: `kit:ferreiro-anao` ──`HAS_SKILL`──> `skill:metalurgia`.

---

### 13. `USES_RULE`
- **Significado**: A entidade opera com base em uma mecânica específica descrita em uma regra base do sistema.
- **Origem Esperada**: `combat`, `ritual_spell`, `power_magic`.
- **Destino Esperado**: `core_rule`.
- **Exemplo**: `combat:manobra-desarme` ──`USES_RULE`──> `rule:teste-de-destreza-resistido`.

---

## 2. Decisões Ontológicas Negativas

### Rejeição de `CAN_CHOOSE_WEAKNESS`
O predicado `CAN_CHOOSE_WEAKNESS` foi formalmente rejeitado sob o princípio de **YAGNI** (You Aren't Gonna Need It) e ausência de precedente canônico no material original analisado. As fontes do sistema Daemon não apresentam menus de seleção para fraquezas opcionais; fraquezas são diretamente possuídas pela entidade (`HAS_WEAKNESS`) ou aprimoramentos negativos gerais adquiridos pelo sistema comum.

---

## 3. Versionamento da Ontologia (Ontology Versioning)

A taxonomia e semântica de relações adota governança de versões estrita:

- **`relations-v1`**: Ontologia inicial. Classificada como **historical / read-only** (somente leitura para fins de histórico e auditoria).
- **`relations-v2`**: Ontologia formal V2. Classificada como **mandatory for new execution** (obrigatório para novas execuções). Toda nova requisição de execução e novo pipeline exige V2.
- É estritamente proibido mesclar dados V1 e V2 em um mesmo arquivo `relations.json` ou pacote de entrega.

---

## 4. Governança e Autoridade Canônica de Compatibilidade

- **Autoridade Canônica Exclusiva**: O arquivo `schemas/relation-compatibility-v2.json` é a única autoridade canônica legível por máquina (`machine-readable JSON = canonical authority`) para determinar a compatibilidade semântica de triplets (`sourceCategory`, `relationType`, `targetCategory`).
- **Documentação Explicativa**: O documento `docs/reference/relation-compatibility-v2.md` possui finalidade unicamente explicativa para leitura humana (`markdown = explanatory only`), sem qualquer duplicação de triplets que possa gerar divergência ou obsolescência.
