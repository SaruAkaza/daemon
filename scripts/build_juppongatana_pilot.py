from __future__ import annotations

import shutil
from collections import Counter
from datetime import UTC, datetime

from common import ROOT, slugify, write_json


SOURCE = "juppongatana"
TITLE = "Juppongatana"
SOURCE_CANDIDATES = [
    ROOT / "Livros" / "word" / "Juppongatana_OCR_alta_qualidade.docx",
    ROOT / "Livros" / "word" / "feito" / "Juppongatana_OCR_alta_qualidade.docx",
]
SOURCE_PATH = next((path for path in SOURCE_CANDIDATES if path.exists()), SOURCE_CANDIDATES[0])
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"


def block(block_id: str, title: str, area: str, paragraphs: list[str]) -> dict:
    return {"id": slugify(block_id), "title": title, "area": area, "paragraphs": paragraphs}


def item(title: str, area: str, kind: str, section_title: str, sections: list[dict]) -> dict:
    paragraphs = [paragraph for section in sections for paragraph in section["paragraphs"]]
    return {
        "id": slugify(title),
        "title": title,
        "area": area,
        "kind": kind,
        "sectionId": slugify(section_title),
        "sectionTitle": section_title,
        "paragraphs": paragraphs,
        "sections": sections,
    }


def npc(
    name: str,
    level: str,
    concept: str,
    attributes: list[str],
    skills: list[str],
    improvements: list[str],
    resources: list[str],
    history: list[str],
    personality: list[str],
    appearance: list[str],
    style: str,
) -> dict:
    sections = [
        block(f"{name}-atributos", "Atributos", "criaturas_npcs", [f"Nível: {level}", *attributes]),
        block(f"{name}-pericias", "Perícias e Combate", "criaturas_npcs", skills),
        block(f"{name}-habilidades", "Habilidades", "criaturas_npcs", [*improvements, *resources]),
        block(f"{name}-historia", "História", "criaturas_npcs", history),
        block(f"{name}-personalidade", "Personalidade", "criaturas_npcs", personality),
        block(f"{name}-aparencia", "Aparência", "criaturas_npcs", appearance),
        block(f"{name}-estilo", "Estilo e Conceito", "criaturas_npcs", [style, f"Conceito: {concept}"]),
    ]
    return {
        "id": slugify(name),
        "name": name,
        "sections": sections,
    }


def make_lore() -> dict:
    return item(
        "Cenarios/Lore - Juppongatana",
        "cenarios_lore",
        "setting",
        "Cenários/Lore",
        [
            block(
                "restauracao-meiji",
                "Do Shogunato para a Restauração Meiji",
                "cenarios_lore",
                [
                    "O Shogunato foi um período da história japonesa comparável ao feudalismo europeu. Com a Restauração Meiji, o Japão deixou o governo ditatorial dos xoguns e iniciou sua abertura ao mundo.",
                    "A chegada do capitão Matthew Perry, com navios de guerra norte-americanos, pressionou o Japão a abrir seus portos. O conflito político resultante alimentou a guerra civil conhecida como Bakumatsu.",
                    "A facção Meiji Ishin reuniu províncias descontentes e lutou por um novo Japão. Em resposta, o governo Edo criou o Shinsengumi, polícia especial em Kyoto encarregada de reprimir os revolucionários.",
                    "Com a vitória da Meiji Ishin, iniciou-se a Era Meiji. As mudanças sociais marginalizaram muitos samurais, que perderam privilégios e passaram a viver como professores, mercenários, criminosos ou andarilhos.",
                ],
            ),
            block(
                "maior-das-batalhas",
                "A Maior das Batalhas",
                "cenarios_lore",
                [
                    "O Juppon Gatana, ou Dez Espadas, é uma tropa de assassinos de elite liderada por Makoto Shishio, antigo agente do governo que sobreviveu à tentativa de execução pelo fogo.",
                    "Shishio reuniu guerreiros como Sohjiro, Yumi, Hoji Sadojima e Uonuma Usui para desafiar o novo governo Meiji.",
                    "Kenshin parte para enfrentar Shishio, acompanhado por aliados como Sano, Kaoru, Yahiko, Misao e Hajime Saitou. A saga termina com a derrota de vários membros do grupo e a morte definitiva de Shishio.",
                ],
            ),
            block(
                "outros-membros",
                "Outros Membros",
                "cenarios_lore",
                [
                    "Saizuchi é o mestre de Fuji e age como estrategista, dando ordens para que Fuji as execute.",
                    "Iwanbou é citado como membro que não atua diretamente nesta saga e ficaria para um suplemento posterior.",
                    "Houji Sadojima é o administrador e organizador do Juppon Gatana, responsável por estruturar o grupo e obter recursos, incluindo a compra da fragata de ferro.",
                    "Yumi foi uma oiran de alto status antes de conhecer Shishio e se tornar sua companheira.",
                ],
            ),
        ],
    )


def make_characters() -> list[dict]:
    return [
        npc(
            "Chyou Sawagejou",
            "7",
            "Colecionador de espadas",
            [
                "Força 12; Constituição 12; Destreza 16; Agilidade 16; Inteligência 12; Força de Vontade 12; Percepção 13; Carisma 14.",
            ],
            [
                "Arte Marcial 35/35; Armas Brancas 45/45 (escolha 4 espadas); Armas Brancas 65/65 (No-Dachi); Esquiva 40%; Acrobacia 40%; Etiqueta 20%; Heráldica 30%; Furtividade 40%; História 20%; Idioma Nativo 30%; Ler e Escrever 30%; Investigação 60%; Interrogatório 45%; Liderança 20%; Impressionar 50%; Lutar com 2 Armas 50%; Rastreio 40%; Sobrevivência 30% (escolha 3 ambientes); Armeiro 40%.",
            ],
            [
                "Aprimoramentos: Bom Senso 1; Aliados 2; Sentidos Aguçados 1; Saúde de Ferro 1; Senso Numérico 1; Mestre 2; Energia Heróica 5; Inimigos -2; Proteger Indefesos -1.",
            ],
            ["Pontos de Vida: 13 + 14; Energia Heróica: 70; Pontos de Fé: 0; Equipamento: katana, No-Dachi e outras espadas."],
            ["Chyou é o membro mais fraco e limitado do Juppongatana em combate direto, mas é um excelente investigador. É conhecido por sua coleção de espadas."],
            ["É calmo, compulsivo por colecionar espadas e, em combate, torna-se convencido e despreza seus adversários."],
            ["Tem porte físico mediano, usa faixa vermelha na cabeça e cabelo loiro arrepiado. Costuma vestir kimono vermelho combinado com sua coleção de espadas."],
            "Kendo Básico.",
        ),
        npc(
            "Henya Kariwa",
            "8",
            "Voador alado",
            ["Força 11; Constituição 11; Destreza 20; Agilidade 20; Inteligência 14; Força de Vontade 14; Percepção 15; Carisma 13."],
            [
                "Arte Marcial 25/25; Armas Brancas 30/30 (escolha 3); Arremesso 65%; Esquiva 50%; Acrobacia 55%; Voo 55%; Etiqueta 20%; Heráldica 30%; Furtividade 55%; História 20%; Idioma Nativo 30%; Ler e Escrever 30%; Investigação 55%; Interrogatório 35%; Liderança 35%; Impressionar 50%; Rastreio 45%; Sobrevivência 30% (escolha 3 ambientes); Armeiro 35%.",
            ],
            [
                "Aprimoramentos: Patrono 2; Sentidos Aguçados 1; Senso Numérico 1; Senso de Direção 1; Energia Heróica 3; Habilidade Especial Voo 2; Inimigos -1; Dever -1.",
            ],
            ["Pontos de Vida: 11 + 8; Energia Heróica: 24; Pontos de Fé: 0; Equipamento: faca e explosivos."],
            ["Henya é fraco individualmente, mas perigoso em conjunto. Sua técnica se baseia em voar e atacar inimigos com explosivos, podendo atingir grandes grupos."],
            ["É convencido por causa de sua técnica de voo explosivo e prefere matar inimigos lentamente."],
            ["É baixo, magro e de estrutura frágil, o que favorece sua técnica de voo. Veste roupa preta lembrando um morcego e tem aparência associada a um corvo."],
            "Voo Explosivo. Sensei desconhecido.",
        ),
        npc(
            "Kamatari Honzo",
            "10",
            "A grande foice",
            ["Força 12; Constituição 12; Destreza 16; Agilidade 16; Inteligência 13; Força de Vontade 14; Percepção 13; Carisma 14."],
            [
                "Perícias do OCR aparecem incompletas no documento. Informação preservada: Armas Brancas 95/95 (katana), além de referências a Arte Marcial, Esquiva, Acrobacia, Etiqueta, Heráldica, Furtividade, História, Idioma Nativo, Ler e Escrever, Investigação, Interrogatório, Liderança, Impressionar, Rastreio, Religião, Ocultismo, Sobrevivência, Meditação, Armeiro, Ferreiro e Pedagogia sem valores legíveis.",
            ],
            ["Aprimoramentos: Bom Senso 1; Aliados 2; Sentidos Aguçados 1; Saúde de Ferro 1; Senso Numérico 1; Mestre 2; Energia Heróica 5; Inimigos -2; Proteger Indefesos -1."],
            ["Pontos de Vida: 12 + 10; Energia Heróica: 40; Pontos de Fé: 0; Equipamento: foice e corrente."],
            ["Kamatari é membro secundário do Juppongatana e sente atração por Shishio. Tenta provar valor seguindo suas ordens."],
            ["Apresenta comportamento alegre e positivo, aceita ordens sem questionar e se esforça para completá-las como forma de demonstrar sentimentos por Shishio."],
            ["Tem aparência feminina, cabelo curto e bem tratado, usa kimono em bom estado e combate com uma grande foice presa a uma corrente."],
            "Honjou.",
        ),
        npc(
            "Fuji",
            "10",
            "Armadura da destruição",
            ["Força 20; Constituição 20; Destreza 12; Agilidade 12; Inteligência 12; Força de Vontade 13; Percepção 12; Carisma 11."],
            [
                "Arte Marcial 30/30; Armas Brancas 30/30 (escolha 5); Armas Brancas 65/65 (katana); Esquiva 40%; Etiqueta 20%; Heráldica 20%; Idioma Nativo 30%; Ler e Escrever 30%; Intimidar 40%; Liderança 30%; Impressionar 50%; Rastreio 30%; Sobrevivência 40% (escolha 6 ambientes); Meditação 40%; Armeiro 30%; Ferreiro 30%.",
            ],
            ["Aprimoramentos: Mestre 1; Saúde de Ferro 1; Inocência 1; Senso de Direção 1; Energia Heróica 5; Inimigos -2; Dever -1."],
            ["Pontos de Vida: 20 + 10; Energia Heróica: 50; Pontos de Fé: 0; Equipamento: katana e armadura completa."],
            ["Fuji é um homem gigantesco rejeitado por sua aparência. Foi quase linchado e acolhido por Saizuchi, a quem serve por gratidão."],
            ["Tem bom caráter, mas vive amargurado por ser tratado como monstro. Deseja uma vida normal e aceitação."],
            ["Tem mais de 3 metros de altura, porte físico enorme, cabelos longos e usa armadura completa feita sob medida."],
            "Kendo Básico. Sensei: Saizuchi.",
        ),
        npc(
            "Anji Yuukyuzan",
            "Monge 3 + Guerreiro 9",
            "Hakai-So",
            ["Força 16; Constituição 16; Destreza 14; Agilidade 14; Inteligência 13; Força de Vontade 13; Percepção 13; Carisma 13."],
            [
                "Arte Marcial 80/80; Armas Brancas 65/65 (faca); Esquiva 70%; Acrobacia 40%; Etiqueta 40%; Heráldica 40%; Furtividade 40%; História 45%; Idioma Nativo 45%; Ler e Escrever 45%; Investigação 25%; Interrogatório 30%; Liderança 45%; Impressionar 50%; Rastreio 35%; Religião 55%; Ocultismo 45%; Sobrevivência 50% (escolha 4 ambientes); Meditação 60%; Pedagogia 60%.",
            ],
            ["Aprimoramentos: Bom Senso 1; Aliados 2; Sentidos Aguçados 1; Saúde de Ferro 1; Senso Numérico 1; Mestre 2; Energia Heróica 4; Inimigos -2; Proteger Indefesos -1."],
            ["Pontos de Vida: 16 + 12; Energia Heróica: 45; Pontos de Fé: 4; Equipamento: faca e Futae no Kiwami."],
            ["Anji era um monge pacífico que cuidava de órfãos no templo budista. Após o templo ser queimado com as pessoas dentro, tornou-se o Deus da Destruição dentro do Juppongatana."],
            ["É um monge renegado que busca agir pelo bem das crianças. Aceitou entrar no grupo se pudesse decidir sobre vida e morte, até contrariando ordens de Shishio."],
            ["O texto não traz descrição física específica para Anji neste DOCX."],
            "Karate. Sensei: alto treinamento.",
        ),
        npc(
            "Usui Uonuma",
            "12",
            "Espada sem luz",
            ["Força 14; Constituição 14; Destreza 14; Agilidade 14; Inteligência 14; Força de Vontade 12; Percepção 18; Carisma 12."],
            [
                "Arte Marcial 30/30; Armas Brancas 30/30 (escolha 4); Tinbeh 40/80; Lança 75/75 (Ro-Chin); Esquiva 55%; Acrobacia 75%; Etiqueta 35%; Heráldica 40%; Furtividade 55%; História 35%; Idioma Nativo 35%; Ler e Escrever 35%; Investigação 40%; Interrogatório 40%; Tortura 65%; Liderança 30%; Impressionar 50%; Rastreio 40%; Religião 20%; Ocultismo 35%; Sobrevivência 40% (escolha 3 ambientes); Meditação 40%; Armeiro 30%; Ferreiro 20%.",
            ],
            ["Aprimoramentos: Bom Senso 1; Aliados 2; Sentidos Aguçados 1; Saúde de Ferro 1; Senso Numérico 1; Mestre 2; Energia Heróica 5; Inimigos -2; Proteger Indefesos -1."],
            ["Pontos de Vida: 13 + 14; Energia Heróica: 70; Pontos de Fé: 0; Equipamento: Ro-Chin e Tinbeh."],
            ["Usui era samurai do xogunato e caçava retalhadores. Após lutar contra Shishio, teve os olhos cortados, ficou cego e treinou até dominar a técnica Shingan."],
            ["Faz parte do Juppongatana por um acordo: quando Shishio apresentar uma brecha, Usui terá o direito de matá-lo."],
            ["Tem porte físico mediano, usa roupas pitorescas com vários olhos e cobre os olhos com uma faixa. Mantém o Tinbeh nas costas até enfrentar adversários perigosos."],
            "Estilo desconhecido.",
        ),
        npc(
            "Sohjiroh Seta",
            "14",
            "Espada Celestial",
            ["Força 12; Constituição 12; Destreza 18; Agilidade 20; Inteligência 13; Força de Vontade 13; Percepção 13; Carisma 13."],
            [
                "Arte Marcial 40/40; Armas Brancas 30/30 (escolha 3); Armas Brancas 92/92 (katana); Esquiva 75%; Acrobacia 55%; Etiqueta 40%; Heráldica 40%; Furtividade 60%; História 25%; Idioma Nativo 30%; Ler e Escrever 30%; Investigação 40%; Interrogatório 40%; Liderança 50%; Impressionar 50%; Rastreio 30%; Luta às Cegas 40%; Sobrevivência 40% (escolha 3 ambientes); Meditação 40%; Armeiro 40%; Ferreiro 20%.",
            ],
            ["Aprimoramentos: Bom Senso 1; Patrono 2; Sentidos Aguçados 1; Senso Numérico 1; Mestre 2; Energia Heróica 5; Inimigos -2."],
            ["Pontos de Vida: 12 + 14; Energia Heróica: 70; Pontos de Fé: 0; Equipamento: katana."],
            ["Braço direito de Makoto Shishio. Após uma infância de abusos, foi poupado e treinado por Shishio depois de presenciar um assassinato e receber dele uma espada."],
            ["É praticamente sem emoção, sempre sorridente e inexpressivo. Essa combinação com seu estilo de luta o torna um inimigo implacável."],
            ["Tem porte físico mediano, usa kimono de cores claras, carrega uma katana na bainha e mantém o rosto sorridente."],
            "Battou-jutsu. Sensei: Makoto Shishio.",
        ),
        npc(
            "Makoto Shishio",
            "15",
            "Anarquista",
            ["Força 16; Constituição 14; Destreza 15; Agilidade 15; Inteligência 15; Força de Vontade 15; Percepção 15; Carisma 15."],
            [
                "Arte Marcial 50/50; Armas Brancas 30/30 (escolha 3); Armas Brancas 95/95 (katana); Esquiva 70%; Etiqueta 40%; Heráldica 40%; Furtividade 50%; História 30%; Idioma Nativo 30%; Ler e Escrever 30%; Investigação 30%; Interrogatório 30%; Liderança 65%; Impressionar 50%; Luta às Cegas 40%; Intimidar 40%; Tortura 40%; Sobrevivência 40% (escolha 5 ambientes); Meditação 30%; Armeiro 40%; Ferreiro 20%; Pedagogia 65%.",
            ],
            ["Aprimoramentos: Aliados 2; Bom Senso 1; Contatos 2; Energia Heróica 5; Grupo de Aliados 3; Herança 2; Recursos 4; Sentidos Aguçados 1; Saúde de Ferro 1; Senso Numérico 1; Inimigos -2; Maldição -3."],
            ["Pontos de Vida: 15 + 15; Energia Heróica: 75; Pontos de Fé: 0; Equipamento: katana Mugenji (2d6+2)."],
            ["Shishio foi sucessor de Battousai durante a Restauração Meiji. O governo tentou eliminá-lo por saber demais, mas ele sobreviveu queimado e passou a construir seu próprio domínio."],
            ["É carismático, determinado e guiado pela filosofia: para os fortes, a vida; para os fracos, a morte."],
            ["Tem corpo coberto por ataduras devido às queimaduras e usa kimono roxo."],
            "Ware Ryu.",
        ),
    ]


def make_techniques() -> list[dict]:
    return [
        item(
            "Battou-jutsu",
            "manobras_combate",
            "technique",
            "Manobras e Especialidades",
            [
                block("battou-jutsu-descricao", "Descrição", "manobras_combate", ["A técnica consiste em sacar a espada rapidamente."]),
                block("battou-jutsu-sistema", "Sistema", "manobras_combate", ["O lutador declara a manobra, recebe -30% no ataque e compara ataque contra defesa. A cada 10% de margem, soma +1 ao dano, com mínimo de +1."]),
                block("battou-jutsu-uso", "Uso", "manobras_combate", ["Usado por Kenshin e Soujiro. Estilo: N/A."]),
            ],
        ),
        item(
            "Futae no Kiwami",
            "manobras_combate",
            "technique",
            "Manobras e Especialidades",
            [
                block("futae-no-kiwami-descricao", "Descrição", "manobras_combate", ["A técnica aplica um golpe e, em intervalo mínimo, um segundo impacto. É difícil de executar, mas muito eficiente."]),
                block("futae-no-kiwami-custo", "Custo", "manobras_combate", ["1 ponto de Energia Heróica; +1 ponto adicional para atingir adversários no campo de visão."]),
                block("futae-no-kiwami-sistema", "Sistema", "manobras_combate", ["Causa 1d8+6 de dano em combate corpo a corpo. Pode ser usado com soco ou chute."]),
                block("futae-no-kiwami-uso", "Uso", "manobras_combate", ["Usado por Anji e Sanosuke. Estilo desconhecido."]),
            ],
        ),
        item(
            "Gatotsu",
            "manobras_combate",
            "technique",
            "Manobras e Especialidades",
            [
                block("gatotsu-descricao", "Descrição", "manobras_combate", ["A técnica consiste em atacar com a espada durante um salto."]),
                block("gatotsu-sistema", "Sistema", "manobras_combate", ["O lutador declara a manobra, recebe -30% no ataque e adiciona +1d6 ao dano."]),
                block("gatotsu-uso", "Uso", "manobras_combate", ["Usado por Saitou. Estilo: Mizoguchi Maitou Ryu."]),
            ],
        ),
        item(
            "Homura-Dama",
            "manobras_combate",
            "technique",
            "Manobras e Especialidades",
            [
                block("homura-dama-descricao", "Descrição", "manobras_combate", ["Com esta manobra, Shishio faz sua espada ser tomada por chamas."]),
                block("homura-dama-custo", "Custo", "manobras_combate", ["2 pontos de Energia Heróica ou 2 Pontos de Vida."]),
                block("homura-dama-sistema", "Sistema", "manobras_combate", ["Acrescenta 2d6 ao dano da espada."]),
                block("homura-dama-uso", "Uso", "manobras_combate", ["Usado por Makoto Shishio. Estilo: Ware Ryu."]),
            ],
        ),
        item(
            "Guren Kaina",
            "manobras_combate",
            "technique",
            "Manobras e Especialidades",
            [
                block("guren-kaina-descricao", "Descrição", "manobras_combate", ["Shishio agarra o adversário pelo rosto e provoca uma explosão."]),
                block("guren-kaina-sistema", "Sistema", "manobras_combate", ["Causa 2d6+1 de dano."]),
                block("guren-kaina-uso", "Uso", "manobras_combate", ["Usado por Makoto Shishio. Estilo: Ware Ryu."]),
            ],
        ),
    ]


def build_payload() -> dict:
    sections = [make_lore(), *make_techniques()]
    characters = make_characters()
    counts = Counter(section["area"] for section in sections)
    counts["criaturas_npcs"] = len(characters)
    return {
        "version": 1,
        "source": SOURCE,
        "title": TITLE,
        "sourceFile": SOURCE_PATH.name,
        "sourcePath": str(SOURCE_PATH.relative_to(ROOT)),
        "status": "pilot_review",
        "summary": "Suplemento de Samurai X sobre o Juppongatana, com contexto histórico, membros em ficha e técnicas de combate.",
        "areas": sorted(counts),
        "groups": [],
        "sections": sections,
        "characters": characters,
        "counts": dict(counts),
        "reviewNotes": [
            "Páginas, cabeçalhos repetidos, agradecimentos e lista de episódios foram removidos da catalogação.",
            "Membros com ficha mecânica foram classificados como Criaturas e NPCs.",
            "Técnicas foram classificadas como Manobras e Especialidades, não como Poderes.",
            "Kamatari tem perícias incompletas no OCR; os campos legíveis foram preservados e a lacuna foi sinalizada no bloco de perícias.",
        ],
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


def move_source_to_done() -> None:
    source_in_word = ROOT / "Livros" / "word" / "Juppongatana_OCR_alta_qualidade.docx"
    if not source_in_word.exists():
        return
    done = ROOT / "Livros" / "word" / "feito" / source_in_word.name
    done.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source_in_word), str(done))


def main() -> None:
    payload = build_payload()
    write_json(OUT_PATH, payload)
    write_json(DOCS_OUT_PATH, payload)
    move_source_to_done()
    print(f"Wrote {OUT_PATH}")
    print(f"Wrote {DOCS_OUT_PATH}")
    print(f"Sections: {len(payload['sections'])}")
    print(f"Characters: {len(payload['characters'])}")


if __name__ == "__main__":
    main()
