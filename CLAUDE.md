# Orientações Para Agentes

Antes de criar ou revisar pilotos de livros Daemon/Trevas, siga as regras de catalogação em:

`docs/reference/cataloging-rules.md`

Em especial:

- antes de qualquer categorização, revise e limpe o texto inteiro do livro com ferramentas e/ou subagents;
- só categorize depois de corrigir OCR/DOCX, palavras coladas, quebras indevidas, mojibake e resíduos de layout;
- não declare `feito` sem regenerar o artefato final, auditar o JSON publicado e conferir amostras reais na estrutura final;
- se restarem trechos ambíguos ou não revisados, declare a pendência em vez de marcar como concluído;
- registre correções em script ou relatório sempre que possível;
- categorias aparecem no hub inicial e filtros/itens ficam dentro da categoria selecionada;
- entidades ficam na lista da categoria selecionada;
- detalhes da entidade ficam na coluna direita;
- aprimoramentos sempre usam `Custo` antes de `Descrição`;
- custo único mostra só o valor;
- custos múltiplos mantêm valor + efeito;
- raças/linhagens só têm `Custo` quando o livro explicita custo de compra/uso; menções soltas a pontos não bastam;
- poderes usam `Pré-requisito` e blocos por `Nível`;
- em NPCs/criaturas, `Perícias e Combate` só recebe ficha operacional; habilidades especiais, poderes internos e efeitos narrativos com dano/teste/uso por dia ficam em bloco próprio (`Habilidades` ou `Poderes`);
- subtítulos nem sempre viram entidades.
