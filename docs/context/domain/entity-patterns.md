# Padrões de Entidades do Sistema Daemon (Entity Patterns)

Este documento fornece as diretrizes canônicas para identificação, diferenciação e modelagem estrutural das entidades do sistema Daemon/Trevas. Ele orienta os agentes a classificar corretamente elementos ambíguos sem depender de adivinhação.

---

## 1. Aprimoramentos (`character_option`)

### Padrão Estrutural Obrigatório
Todo aprimoramento deve apresentar o bloco `Custo` rigorosamente posicionado **antes** do bloco `Descrição`.

```markdown
### Nome do Aprimoramento
- **Custo**: 2 pontos
- **Descrição**: Texto contínuo e fluido detalhando o benefício mecânico e narrativo.
```

### Regras de Modelagem de Custo
- **Custo Único**: Se houver apenas uma opção, o bloco exibe apenas o valor (ex.: `2 pontos`, `3 pontos`), enquanto o efeito específico do custo permanece integrado à `Descrição`.
- **Custos Múltiplos**: Se o aprimoramento oferecer graduações de compra, cada linha deve conter o valor e o benefício concedido:
  - `1 ponto: concede +10% no teste.`
  - `2 pontos: concede +20% no teste e visão no escuro.`
- **Polaridade**: Classificar como positivo, negativo ou sem-marcação (para alimentar o filtro da coluna lateral).

---

## 2. Aprimoramento vs. Kit vs. Raça

A taxonomia Daemon possui particularidades conceituais que exigem atenção rigorosa:

| Tipo | Marcador Diferenciador | Regra Canônica | Exemplo |
| :--- | :--- | :--- | :--- |
| **Aprimoramento** | Custo em pontos, **sem** exigência de perícias. | Pode ser conceitual (define um arquétipo heroico) ou pontual (vantagem isolada). | *Bruto Insano*, *Ciborgue*, *Caçador Sobrenatural*, *Clone da Lenda*. |
| **Kit** | Custo em pontos **e** lista de perícias obrigatórias/sugeridas. | A presença de lista de perícias com porcentagens ou bônus operacionais define o kit. | *Ferreiro Anão*, *Caçador de Bruxas*, *Guerreiro Templário*. |
| **Raça / Linhagem** | Natureza fundamental do ser. | Itens apresentados pelo livro como "Aprimoramentos Raciais" pertencem a `racas` (inclui *Fantasma*, *Revenante*, *Imortal*). Só tem `Custo` se houver custo explícito de compra. | *Elfo*, *Anão*, *Vampiro Lamia*, *Revenante*. |

---

## 3. Raças e Linhagens (`race_lineage`)

- **Regra de Custo**: Só incluir bloco `Custo` se o livro explicitar um valor de compra/seleção da raça. Menções soltas a pontos no texto em outros contextos (ex.: criação geral de personagem, pontos de magia) **não autorizam** a criação de custo.
- **Blocos Internos**: Organizar os blocos reais da obra: `Descrição`, `Poderes Raciais`, `Fraquezas`, `Cultura`, `História`, `Ficha`.

---

## 4. Poderes (`power_magic`)

### Padrão Estrutural por Níveis
Todo poder do sistema Daemon deve ser estruturado em camadas de progressão:

1. **`Pré-requisito`** (quando presente no texto, ex.: `(Alastores)`, `(Cainitas)`, `(Fé 3)`).
2. **`Descrição`**: Texto introdutório ou descritor de casta/origem.
3. **`Nível 1`**, **`Nível 2`**, **`Nível 3`** ...: Cada graduação do poder deve constituir um bloco interno independente, mesmo que no texto original estejam contíguos na mesma linha.

---

## 5. Magias e Rituais (`ritual_spell`)

As magias e rituais operam com metadados estruturados:

- **Agrupamento**: Na interface, as magias são agrupadas por **Caminho** na coluna esquerda (ex.: *Caminho do Fogo*, *Caminho das Trevas*).
- **Campos Canônicos**:
  - `Caminho`: a via mística da magia.
  - `Círculo`: graduação numérica (1 a 6).
  - `Atributo`: atributo de conjuração (normalmente `INT` ou `WILL`).
  - `Custo`: custo em pontos de magia ou rodadas.
  - `Duração`: tempo de duração do efeito.
  - `Alcance`: alcance operacional.
  - `Efeito` / `Descrição`: descrição detalhada do funcionamento da magia.

---

## 6. Criaturas e NPCs (`creature_npc`)

Fichas de monstros, animais e personagens notáveis utilizam o padrão de 4 blocos:

```markdown
### Nome da Criatura / NPC
1. **Atributos**: Atributos primários (CON, FR, DEX, AGI, INT, WILL, PER, CAR), PVs, IP e estatísticas básicas.
2. **Perícias e Combate**: Estritamente ficha operacional — ataques, armas, dano direto, porcentagens de combate e testes.
3. **Habilidades**: Habilidades especiais, poderes internos, efeitos de dano contínuo, venenos, imunidades ou usos diários.
4. **Descrição**: Biografia, história, personalidade e comportamento narrativo.
```

> [!CAUTION]
> **Proibição de Poluição de Ficha**: Frases como *"pode paralisar por 1d6 rodadas"* ou *"causa 2d6 de veneno caso o alvo falhe no teste"* pertencem ao bloco **Habilidades**, e não ao bloco operacional de **Perícias e Combate**. Poderes internos de NPCs não devem ser convertidos em poderes globais para jogadores.

---

## 7. Princípio da Entidade Composta e Subtítulos

- **Subtítulos Não São Entidades**: Um cabeçalho de seção (ex.: "Histórico da Facção", "Personalidade do Chefe", "Locais de Reunião") não deve virar um item independente na lista central. Ele deve ser agrupado como bloco de detalhe da entidade principal correspondente.
