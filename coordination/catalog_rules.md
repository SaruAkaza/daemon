# Cartilha de Catalogação (Daemon/Trevas)

Regras consolidadas. Fonte canônica: `docs/reference/cataloging-rules.md` +
decisões do usuário. Este arquivo é o resumo operacional para os agentes.

## Processo
- **Revisar e limpar o texto inteiro ANTES de categorizar**: OCR, palavras coladas,
  quebras indevidas, mojibake, ligaduras (ﬁ→fi, ﬂ→fl), letras espaçadas
  ("T e n d ê n c i a"→"Tendência), hifenização de coluna ("De-miurgo"→"Demiurgo"),
  resíduos de layout, números de página.
- **Um livro por vez**; registrar correções em script/relatório.
- Não declarar `feito`/`done` sem: regenerar artefato final, auditar o JSON publicado,
  conferir amostras reais na estrutura final e validação visual do usuário.
- Se restarem trechos ambíguos, declarar a pendência em vez de marcar concluído.
- Depois de aprovado, mover o DOCX para `Livros/word/feito`.

## Pipeline de limpeza reutilizável
`scripts/requiem_clean.py`: `dehyphenate` (dicionário pt p/ distinguir quebra de
hífen/ênclise), `join_body` (junta fragmentos), `extract_blocks` (por estilo de
cabeçalho), `normalize` (ligaduras + letras espaçadas). Reaproveitar entre livros.

## Estrutura da aplicação
- Categorias no hub inicial; filtros/itens dentro da categoria.
- Entidades individuais vão no array `sections` de nível superior (cada uma vira
  um item navegável). Um `group` colapsa em UM item — usar para lore/cenário.
- Lore = 1 group por livro: `title` = título do livro, `sectionTitle` = "Cenário".
- Regras base = 1 group: `title` = "Regra base - <Livro>", `sectionTitle` = "Regra Base".

## Aprimoramentos
- Sempre `Custo` antes de `Descrição`. Custo único = só o valor; custos múltiplos =
  valor + efeito por linha.
- Filtro de polaridade na coluna esquerda: positivos / negativos / sem-marcação.

## Aprimoramento vs. Kit vs. Raça
- **Kit**: custo em pontos + perícias.
- **Aprimoramento**: só custo em pontos (mesmo sendo arquétipo conceitual).
- **Raça/Linhagem**: só tem `Custo` quando o livro explicita custo de compra/uso;
  menção solta a pontos não basta.
- (Decisão por livro pode sobrepor — ver contrato do livro.)

## Poderes
- Usam `Pré-requisito` e **blocos por Nível** (cada "Nível N: Nome" é uma subseção;
  o descritor "(Casta)"/intro vai num bloco "Descrição").

## Manobras de Combate
- Categoria própria `manobras_combate`. Cada técnica individual com `Custo` +
  `Descrição` (+ `Pré-requisito`). Não segregar por estilo (decisão do usuário).

## Magias / Rituais
- Categoria `magias`; lista recolhível **por Caminho** na coluna esquerda
  (igual aprimoramentos positivos/negativos). Cada magia individual com
  Caminho/Círculo/Atributo/Custo/Duração/Efeito.

## NPCs / Criaturas (padrão)
- Vão no array `characters[]` com `statBlock` (renderiza 4 blocos):
  **Atributos** (attributes+vitals), **Perícias e Combate** (skills — ficha
  operacional), **Habilidades** (poderes/efeitos especiais), **Descrição** (narrativa).
- `Perícias e Combate` só recebe ficha operacional; habilidades especiais
  (dano/teste/uso por dia) vão em bloco próprio (Habilidades/Poderes).
- Não criar aprimoramentos/poderes a partir de dados internos de NPC.

## Títulos
- Reconstruir nomes truncados pelo corpo (heading "Observadores das" + "95 Teses"
  = "Observadores das 95 Teses"). Dehifenizar cabeçalhos. Descartar back-matter.

## Subtítulos
- Nem todo subtítulo vira entidade.
