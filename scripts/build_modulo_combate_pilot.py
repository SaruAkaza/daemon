from __future__ import annotations

import shutil
from collections import Counter
from datetime import UTC, datetime

from common import ROOT, slugify, write_json


SOURCE = "modulo-combate"
TITLE = "Módulo Combate"
SOURCE_CANDIDATES = [
    ROOT / "Livros" / "word" / "Modulo_Combate_OCR_alta_qualidade.docx",
    ROOT / "Livros" / "word" / "feito" / "Modulo_Combate_OCR_alta_qualidade.docx",
]
SOURCE_PATH = next((path for path in SOURCE_CANDIDATES if path.exists()), SOURCE_CANDIDATES[0])
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"


def block(block_id: str, title: str, area: str, paragraphs: list[str]) -> dict:
    return {"id": slugify(block_id), "title": title, "area": area, "paragraphs": paragraphs}


def item(
    title: str,
    area: str,
    kind: str,
    section_title: str,
    sections: list[dict],
) -> dict:
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


def make_rule_base() -> dict:
    sections = [
        block(
            "lutadores",
            "Lutadores",
            "regras_base",
            [
                "O módulo substitui a lógica tradicional de FA/FD de 3D&T por rolagens diretas de dados para ataque e defesa. Para cada ponto em Força ou Poder de Fogo, o personagem rola 1d e soma os resultados para determinar o dano.",
                "A defesa funciona da mesma forma: cada ponto de Armadura gera 1d, e a soma reduz o dano recebido. O dano restante é subtraído dos Pontos de Vida.",
            ],
        ),
        block(
            "pontos-de-vida",
            "Pontos de Vida",
            "regras_base",
            [
                "Os Pontos de Vida passam a ser sorteados com base na Resistência. O personagem multiplica Resistência por 10 e soma 1d6 ao resultado.",
                "Resistência 0: 1 PV.",
                "Resistência 1: 1d6 + 10 PV.",
                "Resistência 2: 1d6 + 20 PV.",
                "Resistência 3: 1d6 + 30 PV.",
                "Resistência 4: 1d6 + 40 PV.",
                "Resistência 5: 1d6 + 50 PV.",
                "A progressão segue o mesmo padrão para valores maiores de Resistência.",
                "Para recuperar Pontos de Vida, o personagem precisa descansar por pelo menos 8 horas. O Mestre define a recuperação em descansos interrompidos.",
            ],
        ),
        block(
            "pontos-de-magia",
            "Pontos de Magia",
            "regras_base",
            [
                "Pontos de Magia são usados para realizar Manobras Especiais ou Ataques Especiais.",
                "O personagem recebe Pontos de Magia iguais ao valor de Resistência multiplicado por 5.",
                "Resistência 0: 0 PM.",
                "Resistência 1: 5 PM.",
                "Resistência 2: 10 PM.",
                "Resistência 3: 15 PM.",
                "Resistência 4: 20 PM.",
                "Resistência 5: 25 PM.",
                "A progressão segue o mesmo padrão para valores maiores de Resistência.",
                "A recuperação acontece por meditação: a cada 30 minutos, 2 PM são recuperados. Descanso também recupera 2 PM a cada 8 horas.",
            ],
        ),
        block(
            "estrutura-do-combate",
            "Estrutura do Combate",
            "regras_base",
            [
                "O combate é dividido em turnos e rodadas. No início, cada envolvido rola 1d e soma Habilidade para definir a Iniciativa.",
                "A ordem das ações segue do maior valor de iniciativa para o menor. Empates ocorrem simultaneamente.",
                "A iniciativa recebe +1 com Aceleração, +2 com Teleporte, +1 com arma veloz e -1 com arma lenta. Aceleração e Teleporte não são cumulativos.",
                "Em um turno, o personagem pode realizar uma ação e dois deslocamentos, ou três deslocamentos sem ação.",
                "Opcionalmente, quando efeitos alteram a Habilidade durante o combate, o Mestre pode pedir nova rolagem de Iniciativa.",
            ],
        ),
        block(
            "ataque-e-reacao",
            "Ataque e Reação",
            "regras_base",
            [
                "O personagem com maior iniciativa age primeiro e declara seu ataque. Em condições normais, o golpe acerta automaticamente, salvo situações especiais como atacar às cegas ou com a mão ruim.",
                "A vítima escolhe uma reação: Bloqueio, Esquiva ou Contra-Ataque.",
                "Bloqueio: o personagem permanece imóvel e soma o valor fixo de Armadura à rolagem de absorção. Se o bloqueio superar o dano, nenhum dano mínimo é recebido.",
                "Esquiva: o personagem testa Habilidade. Em sucesso, evita todo o golpe; em falha, não pode bloquear e rola apenas Armadura para reduzir o dano.",
                "Ações múltiplas opcionais: o número de defesas e ataques por rodada pode ser limitado pela Habilidade. Abrir mão da ação seguinte permite defender até o dobro da Habilidade.",
            ],
        ),
        block(
            "contra-ataque",
            "Contra-Ataque",
            "regras_base",
            [
                "Contra-ataque simultâneo: o personagem abre mão da defesa e acerta o oponente, mas recebe o ataque normalmente. A Armadura é reduzida ao seu valor mínimo fixo.",
                "Um oponente ferido por contra-ataque perde a sequência de golpes daquele turno.",
                "Contra-ataque resistido: ocorre quando dois combatentes disparam energia um contra o outro usando Poder de Fogo. Os dados são comparados um a um até definir quem vence a disputa.",
                "Manobras Especiais e Ataques Especiais podem ser usados no contra-ataque. No simultâneo, funcionam apenas para ataques baseados em Força; no resistido, exigem Poder de Fogo dos dois lados.",
            ],
        ),
        block(
            "dano",
            "Dano",
            "regras_base",
            [
                "Cada ponto de Força ou Poder de Fogo usado no ataque é convertido em 1d de dano.",
                "Cada ponto de Armadura do alvo é convertido em 1d de absorção. O dano não absorvido reduz os Pontos de Vida.",
                "Todos os ataques causam pelo menos 1 ponto de dano, mesmo quando a Armadura absorve todo o dano. A exceção é o Bloqueio bem-sucedido, que pode anular completamente o dano.",
            ],
        ),
        block(
            "dano-localizado",
            "Dano Localizado",
            "regras_base",
            [
                "Para acertar um local específico, o atacante deve passar em um teste de Habilidade -1. Em falha, o local atingido é definido aleatoriamente.",
                "Tabela de localização: 1 - local escolhido pelo atacante; 2 - cabeça; 3 - tronco; 4 - braços; 5 - pernas; 6 - o atacante erra por se concentrar demais no ponto específico.",
                "Armaduras muito pesadas podem reduzir Habilidade. Some a FD total das proteções e escudos, divida por 4 e compare com a Força. Cada ponto acima da Força gera H-1.",
            ],
        ),
    ]
    return item("Regra base - Módulo Combate", "regras_base", "rule", "Regras Base", sections)


def make_maneuvers() -> list[dict]:
    return [
        item(
            "Manobras Especiais",
            "manobras_combate",
            "technique_rule",
            "Manobras e Especialidades",
            [
                block(
                    "manobras-especiais-descricao",
                    "Descrição",
                    "manobras_combate",
                    [
                        "Manobras Especiais são variações do ataque normal do lutador: golpes secretos que causam efeitos extras além do dano.",
                        "Em jogo, basta declarar a manobra escolhida. Ela causa o dano normal do ataque e aplica o efeito descrito em sua ficha.",
                    ],
                ),
                block(
                    "manobras-especiais-alcance",
                    "Alcance",
                    "manobras_combate",
                    [
                        "Vertical: própria para atingir oponentes acima do personagem, como em saltos ou plataformas.",
                        "Horizontal: usada contra oponentes à frente do personagem.",
                        "Rasteiro: afeta oponentes no chão e à frente do usuário.",
                        "Total: pode ser usada em qualquer situação.",
                        "Usar uma manobra em condição diferente do alcance indicado reduz o dano em -1d. Uma manobra pode ter mais de um alcance.",
                    ],
                ),
                block(
                    "manobras-especiais-limite",
                    "Limite",
                    "manobras_combate",
                    [
                        "O personagem pode conhecer um número de Manobras Especiais igual à sua Habilidade.",
                        "Para aprender uma nova manobra quando já atingiu esse limite, deve esquecer uma manobra antiga.",
                    ],
                ),
                block(
                    "manobras-especiais-extra",
                    "Extra",
                    "manobras_combate",
                    [
                        "Algumas manobras possuem um efeito extra que exige gasto de 1 Ponto de Magia para ser ativado.",
                    ],
                ),
            ],
        ),
        item(
            "Fireball",
            "manobras_combate",
            "technique",
            "Manobras e Especialidades",
            [
                block("fireball-alcance", "Alcance", "manobras_combate", ["Total."]),
                block("fireball-dano", "Dano", "manobras_combate", ["Calor/Fogo."]),
                block("fireball-efeito", "Efeito", "manobras_combate", ["Ataque básico por Poder de Fogo."]),
                block(
                    "fireball-extra",
                    "Extra",
                    "manobras_combate",
                    ["O oponente deve fazer um teste de Resistência para não ser derrubado. Se cair, precisa de 1 turno para se levantar."],
                ),
            ],
        ),
        item(
            "Aerial Strike",
            "manobras_combate",
            "technique",
            "Manobras e Especialidades",
            [
                block("aerial-strike-alcance", "Alcance", "manobras_combate", ["Vertical."]),
                block("aerial-strike-dano", "Dano", "manobras_combate", ["Luz."]),
                block("aerial-strike-efeito", "Efeito", "manobras_combate", ["Ataque básico por Força."]),
                block(
                    "aerial-strike-extra",
                    "Extra",
                    "manobras_combate",
                    ["O oponente deve fazer um teste de Resistência para não ser arremessado. A distância é de 2 metros por ponto de dano causado."],
                ),
            ],
        ),
        item(
            "Yamibarai",
            "manobras_combate",
            "technique",
            "Manobras e Especialidades",
            [
                block("yamibarai-alcance", "Alcance", "manobras_combate", ["Rasteiro."]),
                block("yamibarai-dano", "Dano", "manobras_combate", ["Calor/Fogo."]),
                block("yamibarai-efeito", "Efeito", "manobras_combate", ["Ataque básico por Poder de Fogo."]),
                block(
                    "yamibarai-extra",
                    "Extra",
                    "manobras_combate",
                    ["O oponente fica em chamas e o ataque recebe +1d de dano."],
                ),
            ],
        ),
        item(
            "Super Ataques Especiais",
            "manobras_combate",
            "technique_rule",
            "Manobras e Especialidades",
            [
                block(
                    "super-ataques-custo",
                    "Custo",
                    "manobras_combate",
                    ["Gasta Pontos de Magia em quantidade igual à Habilidade do personagem."],
                ),
                block(
                    "super-ataques-descricao",
                    "Descrição",
                    "manobras_combate",
                    [
                        "O personagem soma a Habilidade ao dano como bônus em dados. Exemplo: Força 2 e Habilidade 4 resultam em +4d no dano.",
                        "Esta versão substitui a antiga vantagem Ataque Especial, que ainda custa 1 ponto.",
                        "Depois de usar o Super Ataque Especial, o personagem fica exausto e sua Habilidade é considerada 0 no próximo turno.",
                        "Como variante, o personagem pode usar apenas metade da Habilidade no ataque e conservar a outra metade para o turno seguinte.",
                    ],
                ),
            ],
        ),
    ]


def make_equipment() -> list[dict]:
    return [
        item(
            "Pistola",
            "itens_equipamentos",
            "equipment",
            "Itens e Equipamentos",
            [
                block("pistola-ficha", "Ficha", "itens_equipamentos", ["Alcance: 15 m.", "SDT: 1.", "Pente: 7.", "Dano: 2d+2."]),
                block("pistola-descricao", "Descrição", "itens_equipamentos", ["Arma leve, geralmente usada com apenas uma das mãos e adequada a combate rápido."]),
            ],
        ),
        item(
            "Metralhadora",
            "itens_equipamentos",
            "equipment",
            "Itens e Equipamentos",
            [
                block("metralhadora-ficha", "Ficha", "itens_equipamentos", ["Alcance: 25 m.", "SDT: 5.", "Pente: 30.", "Dano: 3d+1."]),
                block("metralhadora-descricao", "Descrição", "itens_equipamentos", ["Arma média para ataques em massa, capaz de realizar vários disparos no mesmo turno."]),
            ],
        ),
        item(
            "Escopeta",
            "itens_equipamentos",
            "equipment",
            "Itens e Equipamentos",
            [
                block("escopeta-ficha", "Ficha", "itens_equipamentos", ["Alcance: 10 m.", "SDT: 1.", "Pente: 5.", "Dano: 4d+3."]),
                block("escopeta-descricao", "Descrição", "itens_equipamentos", ["Arma pesada de combate, usada com as duas mãos. Personagens com Força 0 ou 1 sofrem recuo intenso."]),
            ],
        ),
        item(
            "Arco",
            "itens_equipamentos",
            "equipment",
            "Itens e Equipamentos",
            [
                block("arco-ficha", "Ficha", "itens_equipamentos", ["Alcance: 25 m.", "SDT: igual ao Poder de Fogo.", "Pente: não se aplica.", "Dano: 1d."]),
                block("arco-descricao", "Descrição", "itens_equipamentos", ["Arma de ataque à distância em cenários medievais. Arcos modernos com mira acrescentam +3 ao dano."]),
            ],
        ),
        item(
            "Armas Brancas",
            "itens_equipamentos",
            "equipment_group",
            "Itens e Equipamentos",
            [
                block(
                    "armas-brancas-regras",
                    "Regras",
                    "itens_equipamentos",
                    [
                        "O ataque com arma branca funciona como um ataque desarmado: o personagem declara o ataque e acerta automaticamente em condições normais.",
                        "Armas brancas podem causar dano por Força quando usadas em combate corpo a corpo ou por Poder de Fogo quando arremessadas.",
                    ],
                ),
                block(
                    "armas-brancas-lista",
                    "Lista",
                    "itens_equipamentos",
                    [
                        "Espada Leve: F+1d+4; PdF+2d+6; veloz.",
                        "Espada Média: F+2d+4; PdF+2d+5.",
                        "Espada Pesada: F+3d+2; PdF+2d+6; duas mãos; vorpal.",
                        "Machado de Arremesso: F+1d+3; PdF+2d+5.",
                        "Machado Leve: F+2d+4; PdF+1d+5.",
                        "Machado Pesado: F+3d+5; PdF+2d+3; duas mãos; vorpal.",
                        "Maça: F+2d+2; PdF+2d+4.",
                        "Mangual: F+2d+6; PdF+2d+5; Ataque Múltiplo.",
                        "Foice: F+2d+2; PdF+1d+1; duas mãos.",
                        "Marreta: F+3d+4; PdF+2d+1; duas mãos.",
                        "Lança Comum: F+2d+5; PdF+2d+4; duas mãos.",
                        "Lança de Guerra: F+2d+7; PdF+2d+10; duas mãos.",
                        "Bastão de Treino: F+1d+6; PdF+1d+1; duas mãos.",
                        "Bastão de Combate: F+2d+1; PdF+2d+5; duas mãos.",
                        "Shuriken: F+2; PdF+4; veloz.",
                        "Faca/Adaga: F+4; PdF+1d.",
                        "Punhal: F+1d+1; PdF+6; veloz.",
                        "Cajado: F+1d; PdF+3.",
                        "Cetro: F+1d+5; PdF+1d.",
                    ],
                ),
            ],
        ),
        item(
            "Armaduras",
            "itens_equipamentos",
            "equipment_rule",
            "Itens e Equipamentos",
            [
                block(
                    "armaduras-descricao",
                    "Descrição",
                    "itens_equipamentos",
                    [
                        "As proteções são divididas em cinco partes: cabeça, tronco, braços, pernas e proteção total.",
                        "Na descrição das peças aparece a Força de Defesa (FD), somada ao resultado final do teste de Armadura quando o local protegido é atingido.",
                        "Exemplo: um personagem com Armadura 2 e elmo de FD 1 rola 2d+1 quando atingido na cabeça.",
                    ],
                ),
            ],
        ),
    ]


def build_payload() -> dict:
    sections = [make_rule_base(), *make_maneuvers(), *make_equipment()]
    counts = Counter(section["area"] for section in sections)
    return {
        "version": 1,
        "source": SOURCE,
        "title": TITLE,
        "sourceFile": SOURCE_PATH.name,
        "sourcePath": str(SOURCE_PATH.relative_to(ROOT)),
        "status": "pilot_review",
        "summary": "Módulo alternativo de combate para 3D&T, com regras de dano, PV, PM, manobras especiais, armas e armaduras.",
        "areas": sorted(counts),
        "groups": [],
        "sections": sections,
        "counts": dict(counts),
        "reviewNotes": [
            "Editorial, créditos, páginas vazias e marcas de OCR foram removidos da catalogação.",
            "O núcleo do livro foi tratado como uma única regra base, pois os subtópicos explicam o mesmo módulo de combate.",
            "Manobras Especiais e Super Ataques Especiais foram catalogados em Manobras e Especialidades, não em Poderes.",
            "Armas e armaduras foram separadas como Itens e Equipamentos, com fichas em linhas próprias para evitar aglutinação.",
        ],
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


def move_file(source: str, target_dir: str) -> None:
    source_path = ROOT / "Livros" / "word" / source
    if not source_path.exists():
        return
    target_path = ROOT / "Livros" / "word" / target_dir / source_path.name
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source_path), str(target_path))


def main() -> None:
    payload = build_payload()
    write_json(OUT_PATH, payload)
    write_json(DOCS_OUT_PATH, payload)
    move_file("Modulo_Combate_OCR_alta_qualidade.docx", "feito")
    move_file("Compendio de regras DAEMON Trevas.docx", "corrigir")
    print(f"Wrote {OUT_PATH}")
    print(f"Wrote {DOCS_OUT_PATH}")
    print(f"Sections: {len(payload['sections'])}")


if __name__ == "__main__":
    main()
