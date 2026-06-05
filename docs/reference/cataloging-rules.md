# Regras de Catalogação Daemon/Trevas

Este documento registra regras de tratamento que devem ser seguidas por qualquer agente trabalhando nos pilotos ou no pipeline final.

## Etapa Obrigatória Antes da Categorização

Antes de categorizar qualquer livro, revise e limpe o texto inteiro do livro. A categorização só deve começar depois que o texto-base estiver suficientemente confiável.

Fluxo obrigatório:

- Auditar o texto do livro com ferramentas e/ou subagents antes de criar entidades.
- Procurar e corrigir problemas de OCR/DOCX: caracteres de controle, mojibake, símbolos no meio de palavras, palavras coladas, quebras indevidas, hifenização quebrada, cabeçalhos/rodapés residuais e fragmentos de layout.
- Validar exemplos reais dos achados antes de aplicar regras amplas. Trocas globais só devem ser usadas quando o padrão for inequívoco.
- Registrar as correções em script ou relatório sempre que possível, para que o processo seja reexecutável e auditável.
- Só depois da revisão textual fazer a segmentação semântica e categorização em regras base, cenários/lore, poderes, aprimoramentos, raças, NPCs etc.

Motivo: texto sujo gera categorização ruim. Se uma seção está quebrada, colada ou com OCR incorreto, ela deve ser tratada primeiro como problema textual, não como problema de classificação.

## Critério Para Marcar Como Feito

Não marcar um livro, categoria ou ajuste textual como `feito` apenas porque o trecho reportado foi corrigido.

Antes de dizer que está feito:

- Regenerar o artefato final usado pela aplicação.
- Auditar o JSON final publicado, não apenas o script ou o texto-fonte.
- Procurar padrões de alta confiança: ligaturas quebradas (`ffi`, `ffl`), OCR óbvio, palavras coladas, letras trocadas por números, `l` usado como `1`, mojibake e títulos deformados.
- Conferir manualmente amostras reais das seções alteradas na estrutura final.
- Verificar que a aplicação/servidor está lendo o arquivo atualizado.
- Se ainda houver trechos ambíguos ou não revisados, declarar como pendência. Nesse caso, o correto é dizer `corrigido nesta rodada` ou `auditado parcialmente`, não `feito`.

Motivo: o usuário não deve precisar revisar novamente logo depois de uma confirmação de conclusão. A confirmação precisa representar uma checagem criteriosa do artefato final.

## Estrutura de Navegação

- A barra lateral esquerda lista categorias/segmentos gerais: regras base, cenários e lore, poderes, aprimoramentos, rituais, raças, criaturas e NPCs, itens e equipamentos etc.
- A coluna central lista entidades da categoria selecionada.
- A coluna direita detalha a entidade selecionada em blocos internos.
- Nem todo subtítulo vira item na coluna central. Subtítulos podem ser apenas blocos internos de uma entidade maior.

## Entidades Compostas

Use entidade composta quando várias seções descrevem a mesma coisa.

Exemplos:

- Um NPC aparece como um item em `Criaturas e NPCs`; ficha, história, personalidade, poderes internos e curiosidades são blocos internos.
- Um cenário/lore pode aparecer como um item único; histórico, organizações, locais e contexto ficam como blocos internos.
- Uma aventura pode aparecer como um item único; introdução, fases e cenas ficam como blocos internos.
- Uma regra base ampla pode aparecer como um item único; subtópicos de regra ficam como blocos internos.

## Regras Base e Cenários — Aglutinação por Livro

Regras Base e Cenários e Lore devem ser aglutinados por livro: todas as seções de um mesmo livro formam **um único item** na coluna central, com os tópicos individuais como blocos de detalhe na coluna direita.

O item agregado de Regras Base deve usar o título padrão `Regra base - Nome do livro`.

Exceção para Cenários: se o livro contiver **cenários completamente distintos** (ex.: um livro com um módulo urbano e um módulo espacial independentes, cada um com lore próprio e sem ligação temática), cada cenário distinto pode ser um item separado na coluna central.

Não é exceção: seções de um mesmo cenário divididas em capítulos (história, organizações, locais, linha do tempo) — essas ficam todas como blocos de detalhe do mesmo item.

Exemplos:

- Anime RPG Powers tem regras de sistema e vários tópicos de lore → um item "Regra base - Anime RPG - Powers" e um item "Cenários e Lore"
- Um livro que cobre vampiros E robôs espaciais sem ligação → dois itens de cenário separados são aceitáveis
- Um livro de campanha com introdução, lore, facções e locais → tudo em um único item de cenário

## Aprimoramentos vs. Kits vs. Raças

A distinção entre aprimoramento, kit e raça no sistema Daemon:

- **Aprimoramento**: tem custo em pontos de aprimoramento. Não exige perícias. Pode ser conceitual (define arquétipo de herói) ou pontual (vantagem isolada). Exemplo: Bruto Insano, Ciborgue, Caçador Sobrenatural.
- **Kit**: tem custo em pontos de aprimoramento **e** lista de perícias obrigatórias e/ou sugeridas. A presença de perícias é o marcador que diferencia um kit de um aprimoramento conceitual.
- **Raça**: quando o livro apresenta itens como "Aprimoramentos Raciais", todos vão para `racas` — independente de representarem espécie biológica ou condição adquirida (Fantasma, Revenante, Imortal incluídos). O critério é a intenção do livro de definir a natureza fundamental do ser, não a origem biológica ou temporal da condição.

Portanto, itens como "Bruto Insano", "Ciborgue", "Caçador Sobrenatural", "Clone da Lenda" permanecem em `aprimoramentos` pois não possuem custo em perícias nem são apresentados como raça pelo livro.

Quando um item tiver estrutura de kit — especialmente `Custo` em pontos de aprimoramento e/ou perícia + bloco/lista de `Perícias` — catalogar em `kits`, com tipo `kit`, não em `classes`. Exemplo: Ferreiro, Guerreiro, Ladrão, Clérigo e Mago em `Anões` são kits porque têm custo e perícias definidos.

## Aprimoramentos

Todo aprimoramento deve ser detalhado com `Custo` antes de `Descrição`.

Regra para o bloco `Custo`:

- Se houver apenas uma opção de custo, mostrar apenas o valor.
  - Exemplo: `2 pontos`
  - Exemplo: `3 Pontos`
- Mesmo quando houver apenas uma opção, o efeito desse custo deve aparecer na `Descrição`.
- Se houver múltiplas opções de custo, cada linha deve manter o valor e o que aquele custo concede.
  - Exemplo: `1 ponto: recebe um benefício menor.`
  - Exemplo: `2 pontos: recebe um benefício maior.`

Regra para o bloco `Descrição`:

- Deve aparecer abaixo de `Custo`.
- Deve ser um texto contínuo, sem quebras indevidas vindas do DOCX/OCR.
- Se existir uma descrição geral antes das opções de custo, usar essa descrição geral.
- Se não existir descrição geral separada, usar os efeitos das opções de custo como descrição contínua.

## Raças e Linhagens

Raças/linhagens só devem ter bloco `Custo` quando o livro informar explicitamente um custo de compra, uso ou seleção da raça.

Regra para custo em `Raças`:

- Se o livro apresenta um valor explícito junto da raça, criar bloco `Custo`.
  - Exemplo: `1 ponto`
  - Exemplo: `2 pontos`
- Se o texto apenas menciona pontos em outro contexto, vantagens, poderes, criação de personagem ou progressão, não inferir automaticamente que isso é custo da raça.
- Se não houver custo explícito, a raça deve ser detalhada apenas com seus blocos reais: `Descrição`, `Poderes Possíveis`, `Fraquezas`, `Cultura`, `História`, `Ficha`, etc.
- O filtro `Custo` para `Raças` só deve aparecer quando houver raças com bloco `Custo` no livro/categoria.

Exemplos dos pilotos atuais:

- `Anime RPG - Powers`: raças possuem `Custo` explícito e devem manter esse bloco.
- `Animalidade`: raças/linhagens não possuem custo explícito catalogado; não criar custo.
- `Aliança Daemon 01 / Ghul`: menções soltas a pontos não devem virar `Custo` sem confirmação textual explícita.

## Poderes

Todo poder deve ser detalhado assim:

- Primeiro bloco: `Pré-requisito`, quando o texto informar algo como `(Alastores)`, `(Cainitas)` etc.
- Em seguida, um bloco por nível: `Nível 1`, `Nível 2`, `Nível 3` etc.
- Quando vários níveis estiverem grudados na mesma linha, separar cada ocorrência de `Nível X:` em bloco próprio.

## NPCs e Criaturas

- Atributos como `CON`, `FR`, `DEX`, `AGI`, `INT`, `WILL`, `PER`, `CAR`, `PV` e `IP` pertencem ao bloco de ficha/atributos.
- Ataques, dano, porcentagens de perícias e armas pertencem ao bloco de perícias/combate.
- Habilidades especiais, poderes internos, efeitos narrativos de combate e descrições de uso de poderes devem ficar em bloco próprio do NPC/criatura, normalmente `Habilidades` ou `Poderes`, e não dentro de `Perícias e Combate`.
- `Perícias e Combate` deve conter apenas dados operacionais de ficha: ataques, armas, dano direto de ataque, perícias com porcentagem/teste e manobras listadas como ficha.
- Frases explicativas como "pode causar...", "pode usar...", "caso o alvo...", "seu item/poder..." ou "vezes por dia" são habilidade/efeito, mesmo quando mencionam dano, teste, veneno ou rodada.
- Esta separação vale para todos os livros anteriores e futuros para manter coerência entre fichas de criaturas/NPCs.
- História, curiosidades e personalidade específicas de um NPC não devem virar `Cenários e Lore` global.
- Poderes internos de NPC não devem virar categoria global `Poderes`.

## Limpeza de Texto

- Juntar hifenização quebrada: `fa-` + `ces` -> `faces`.
- Juntar fragmentos quando o parágrafo anterior ficou aberto.
- Juntar linhas iniciadas por modificador/bônus quando a linha anterior ficou aberta: `você ganha` + `+3 Poderes...`.
- Remover assinaturas soltas de citação quando forem ruído isolado.
- Preservar bullets/listas quando forem conteúdo real.
