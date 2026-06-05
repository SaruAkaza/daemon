from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

from docx import Document

from common import ROOT, slugify, write_json


SOURCE = "anjos-a-cidade-de-prata"
SOURCE_PATH = ROOT / "Livros" / "word" / "feito" / "Anjos_A_Cidade_de_Prata.docx"
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"


def fix_spaced_letters(text: str) -> str:
    """Colapsa sequencias OCR do tipo 'ORI G E m' -> 'ORIGEM'."""
    text = text.replace('	', ' ')
    char_class = r'[A-Za-záàãâéêíóôõúüçÁÀÃÂÉÊÍÓÔÕÚÜÇ]'
    pattern = rf'(?<!\w)((?:{char_class} ){{2,}}{char_class})(?!\w)'
    return re.sub(pattern, lambda m: m.group(0).replace(' ', ''), text)


def normalize_text(text: str) -> str:
    # 1. Ligaduras Unicode (PRIMEIRO — afeta tudo abaixo)
    text = text.replace('ﬁ', 'fi')   # ﬁ ligatura fi
    text = text.replace('ﬂ', 'fl')   # ﬂ ligatura fl
    text = text.replace('ﬃ', 'ffi')  # ﬃ ligatura ffi
    text = text.replace('ﬄ', 'ffl')  # ﬄ ligatura ffl

    # 2. Símbolo £ (antes de outros fixes pois £ aparece em palavras corrompidas)
    text = text.replace('£SCLHA', 'ESCOLHA')
    text = text.replace('H£RIUES', 'HERCULES')
    text = text.replace('REBEU£', 'REBELIÃO')
    text = re.sub(r'£', 'E', text)

    # 3. Artefatos específicos conhecidos (após ligaduras e £ já resolvidos)
    text = text.replace('OLYfflPUS', 'Olympus')
    text = text.replace('CAfflPANHA', 'CAMPANHA')
    text = text.replace('fflAGlA', 'MAGIA')
    text = text.replace('NlffiBUS', 'NIMBUS')
    text = text.replace('BURffiCRATAS', 'BUROCRATAS')
    text = text.replace('VENENffiES', 'VENENOS')
    text = text.replace('RffiDADA', 'RODADA')
    text = text.replace('SffimANDffi', 'SOMANDO')
    text = text.replace('Hl£ffi OPffiSTA', 'HASTE OPOSTA')
    text = text.replace('CefflBATÊ', 'COMBATE')
    text = text.replace('CefflBAT£', 'COMBATE')
    text = text.replace('açãd', 'ação')
    text = text.replace('Urri ', 'Um ')
    text = re.sub(r'j á\b', 'já', text)

    # 4. Corrigir OCR comum neste livro (substituições herdadas)
    text = text.replace(" ", " ")
    text = text.replace("Clidade", "Cidade")
    text = text.replace("NlDIBUS", "NIDIBUS")
    text = text.replace("PU'TICA", "POLÍTICA")
    text = text.replace("RATmARAN", "KATMARAN")
    text = text.replace("BfiNCÃ", "BÊNÇÃO")
    text = text.replace("CemuNHÃO", "COMUNHÃO")
    text = text.replace("CNTR0Lfi niENTAL", "CONTROLE MENTAL")
    text = text.replace("ÊNfiRGIZACÃO", "ENERGIZAÇÃO")
    text = text.replace("IIIfiNSAGfilR CfiLfiSTIAL", "MENSAGEIRO CELESTIAL")
    text = text.replace("LfiXTALiems", "LEXTALIEMS")
    text = text.replace("NlffiBUS", "NIMBUS")
    text = text.replace("PAssAGfim ASTRAL", "PASSAGEM ASTRAL")
    text = text.replace("PfiRCfiPCÃ DIVINA", "PERCEPÇÃO DIVINA")
    text = text.replace("QUfiRUBIA", "QUERUBIA")
    text = text.replace("RfiGENfiRACAO", "REGENERAÇÃO")
    text = text.replace("SimuiACRe", "SIMULACRO")
    text = text.replace("TfiLECINlSIA", "TELECINESIA")
    # OCR: inline sub-headers de castas que vazam para o texto do parágrafo
    text = text.replace("TaeNes ", "Tronos ")
    text = text.replace("Peo6R. es ÚCOS", "Poderes Únicos:")
    text = text.replace("PODERES ÚNices", "Poderes Únicos:")
    text = text.replace("PeDÊRfis ÚNices", "Poderes Únicos:")
    text = text.replace("P0DERÊS ÚNICffiS DS ANJfflS G ARCANJffiS", "Poderes Únicos dos Anjos e Arcanjos:")
    text = text.replace("PffiDERfiS ÚN! COS", "Poderes Únicos:")
    text = text.replace("P0D6RES ÚNIC0S", "Poderes Únicos:")
    text = text.replace("A ORIGEffl", "A Origem")
    text = text.replace("CAmPANHA", "Campanha")
    text = text.replace("CAfflPANHA", "Campanha")
    text = text.replace("HlAGffiS", "Magos")
    # OCR: inline sub-headers de lore
    text = text.replace("A HisréRiA De PARDÍSIA", "A História de Pardíssia")
    text = text.replace("HlETRéPeus", "Metrópolis")
    text = text.replace("A CIDADE DeURADA DE RA", "A Cidade Dourada de Ra")
    text = text.replace("0 SeLARium", "O Solarium")
    text = text.replace("0 cetnec", "O começo —")
    text = text.replace("As PiRAmiDEs", "As Pirâmides")
    # OCR: inline sub-headers de regras
    text = text.replace("3. VERIflQUE DETALHCS DA HISTÓRIA.", "3. Verifique Detalhes da História.")
    text = text.replace("DEFINA S PONTOS DG IIlAGIA fi OS FOCUS,", "Defina os Pontos de Magia e os Focus.")
    text = text.replace("ITIeDipicADeR DE ARIHA", "Modificador de Arma")
    text = text.replace("IIIeDiFicADeR DE ARIHA TTIÁGICA", "Modificador de Arma Mágica")
    text = text.replace("IIIeDIFICADeR DE IIlAGIA", "Modificador de Magia")
    text = text.replace("ACÊRTS CRÍTICO", "Acerto Crítico")
    text = text.replace("ATAQues FeRA DÊ ALCANCE", "Ataques Fora de Alcance")
    text = text.replace("HlÂffi OPffiSTA", "Mão Oposta")
    text = text.replace("CmBATÊ NA ÍIleRTAt", "Combate Mortal")
    text = text.replace("ffi QU6 es VAISRES SIGNIMCAJII?", "O Que os Valores Significam?")
    # OCR: letra espaçada específica deste livro
    text = text.replace("ORI G E m", "ORIGEM")
    # OCR: dígitos confundidos com letras (l=1, O=0) — herdados
    text = text.replace(" l d l O ", " 1d10 ")
    text = text.replace(" l d l O.", " 1d10.")
    text = text.replace(" l d l O,", " 1d10,")
    text = text.replace(" l d l O)", " 1d10)")
    text = text.replace("l dó", "1d6")
    text = text.replace("ldó", "1d6")
    text = text.replace("3 dó", "3d6")
    text = text.replace("2 dó", "2d6")
    text = text.replace(" l P V ", " 1 PV ")
    text = text.replace(" l P V.", " 1 PV.")
    text = text.replace(" l P V,", " 1 PV,")
    text = text.replace(" l O minutos", " 10 minutos")
    text = text.replace(" l O l ", " 101 ")
    text = text.replace(" l O ", " 10 ")
    text = text.replace("l OOm", "100m")
    text = text.replace("j ogam", "jogam")
    text = text.replace("ffi Diluvie", "O Dilúvio")
    text = text.replace("ffi Dilúvio", "O Dilúvio")
    # OCR: inline sub-headers adicionais
    text = text.replace("9. PERÍCIAS cem ARIHAS E PERÍCIAS cemuNs", "9. Perícias com Armas e Perícias Comuns")
    text = text.replace("CRIANDO srus paépRiO ITENS mAcices", "Criando Seus Próprios Itens Mágicos")
    text = text.replace("I. Â£SCLHA A CAfflPANHA", "1. Escolha a Campanha")
    text = text.replace("I. ESCOLHA A CAfflPANHA", "1. Escolha a Campanha")
    text = text.replace("DATAS, LCAIS e CASTA", "4. Datas, Locais e Casta")
    text = text.replace("6. EsceiHA Os PODERES ANGELICAIS", "6. Escolha os Poderes Angelicais")
    text = text.replace("7. Penres DE ApRimeRAmENTe", "7. Escolha os Aprimoramentos.")
    text = text.replace("10. PNTS DÃŠ VIDA E ÃNDICE DE PRTECÃ", "10. Pontos de Vida e Ãndice de ProteÃ§Ã£o.")
    text = text.replace("11. SE? ER. sNAGem Ã¨ um IIIAG.", "11. Se o Personagem Ã© um Mago.")
    text = text.replace("12. ITENS mÃGices", "12. Itens MÃ¡gicos.")
    text = text.replace("13. REUNINDO Os PERSONAGENS", "13. Reunindo os Personagens")
    text = text.replace("OUTRS PDfiRfiS", "Outros Poderes")
    text = text.replace("CeniBATE", "Combate")
    text = text.replace("AovERse", "Adverso")
    text = text.replace("H! RRfiND", "Morrendo")
    text = text.replace("QUfiDAS", "Quedas")
    text = text.replace("VENENffiS", "Venenos")
    text = text.replace("OB}fiTOs ilÍÁGECes", "Objetos Mágicos:")
    text = text.replace("OB}fiTOs ilIÁGECes", "Objetos Mágicos:")
    text = text.replace("PACres variável:", "Pactos — variável:")
    text = text.replace("PACres", "Pactos")
    text = text.replace("CfflNTATS", "Contatos")
    text = text.replace("ClfiR", "Clérigo")
    text = text.replace("\\ ponto:", "1 ponto:")  # Objetos Mágicos OCR: \ ponto: -> 1 ponto:
    text = text.replace("DAN0", "Dano")
    text = text.replace("SffimANDffl ATRIBUTOS", "Somando Atributos")
    # OCR: remover artefatos de tabela que ficam isolados como parágrafo
    if re.fullmatch(r"ZÁS|ÍA.*|O\*y.*|J-J.*|IfJ.*|Ativo ffi.*|l~t\.*|Fracasso Automático.*|Sucesso automático.*", text):
        return ""
    text = text.replace("SUCESSS e FRACASSO AuremATices", "Sucessos e Fracassos Automáticos")
    text = text.replace("mesrno", "mesmo")
    text = text.replace("PIAN0S DE EXISTÊNCIA", "Planos de Existência")
    bad_a = chr(0x00C3)
    text = text.replace(f"A INQUISIC{bad_a}", "A Inquisição")
    text = text.replace(f"INVAS{bad_a}O", "INVASÃO")
    text = text.replace(f"N{bad_a}O", "NÃO")
    text = text.replace(f"BÊNÇ{bad_a}O", "BÊNÇÃO")
    text = text.replace(f"CRIAÇ{bad_a}O", "CRIAÇÃO")
    text = text.replace(f"PRTEC{bad_a}", "PROTEÇÃO")
    text = text.replace("ÍNDICE DÊ PROTEÇÃO", "Índice de Proteção")
    text = text.replace("Pontos de Vida E Índice de Proteção", "Pontos de Vida e Índice de Proteção")
    text = text.replace("PNTS DÊ VIDA", "Pontos de Vida")
    text = text.replace(f"ORGANIZAC{bad_a}0", "Organização")
    text = text.replace(f"ORGANIZAC{bad_a}e", "Organização")
    text = text.replace("ORGANIZACAO", "Organização")
    text = text.replace("ORGANIZACAe", "Organização")
    text = text.replace("PODfiRfiS ÚNICOS", "Poderes Únicos:")
    text = text.replace("PODfiRfiS", "Poderes")
    text = text.replace("Alifica", "Ali fica")
    text = text.replace("deEdwardDeVere", "de Edward De Vere")
    text = text.replace("amanhecerão mesmo tempo", "amanhecer ao mesmo tempo")
    text = text.replace("certaforma", "certa forma")
    text = text.replace("deusas~e", "deusas e")
    text = text.replace("no finaldeste", "no final deste")
    text = text.replace("Jogase", "Joga-se")
    text = text.replace('conhecer"quemmanda em quem"', 'conhecer "quem manda em quem"')
    text = text.replace("deulhe", "deu-lhe")
    text = text.replace("mante-los", "mantê-los")
    text = text.replace("metereologia", "meteorologia")
    text = text.replace("inciativa", "iniciativa")
    text = text.replace("Spiriíum", "Spiritum")
    text = text.replace("par a o", "para o")
    text = text.replace("medida abstraia", "medida abstrata")
    text = text.replace("ninas especiais", "runas especiais")
    text = text.replace('desco"brir', "descobrir")
    text = text.replace("prote- cão", "proteção")
    text = text.replace("histo- ricamente", "historicamente")
    text = text.replace("con- trole", "controle")
    text = text.replace("ope- rações", "operações")
    text = text.replace("aumen- tados", "aumentados")
    text = text.replace("mani- festam", "manifestam")
    text = text.replace("4- CALCULA-SE es ACERTOS E DANCS", "4- Calcula-se os Acertos e Danos")
    text = text.replace("A PfiSTS", "A Peste")
    text = text.replace("AirnA DUPLA", "Alma Dupla")
    text = text.replace("fisceLHA UfflA HISTéRIA fflRTAL", "Escolha uma História Mortal.")
    text = text.replace("fisceLHA seus ATRIBUTOS", "Escolha seus Atributos.")
    text = text.replace("fisceiHA Os iNimices De PSRseNAGEm", "Escolha os Inimigos de Personagem.")
    text = text.replace("Primeira Pergunta l.", "Primeira Pergunta 1.")
    text = text.replace("Personalidade: l.", "Personalidade: 1.")
    text = text.replace("Fase l", "Fase 1")
    text = text.replace("aproximadamente l m", "aproximadamente 1 m")
    text = text.replace("penumbra de l m", "penumbra de 1 m")
    text = text.replace("0B|ETes ITIÁGices", "Objetos Mágicos")
    text = text.replace("-l.", "-1.")
    text = text.replace("AumeNTe DE ATRiBures", "Aumento de Atributos")
    text = text.replace("SOkgs", "50kgs")
    text = text.replace("ofajetos", "objetos")
    text = text.replace("lOm", "10m")
    text = text.replace("lOOm", "100m")
    text = text.replace("1OOKg", "100Kg")
    text = text.replace("1OOkgs", "100kgs")
    text = text.replace("2dó", "2d6")
    text = text.replace("1dó", "1d6")
    text = text.replace("formase", "forma-se")
    text = text.replace("dementai", "mental")
    text = text.replace("l km", "1 km")
    text = text.replace("l hora", "1 hora")
    text = text.replace("l vez", "1 vez")
    text = text.replace("l trovão", "1 trovão")
    text = text.replace("l d de efeitos", "1d de efeitos")
    text = text.replace("0 anjo", "O anjo")
    text = text.replace("0 valor", "O valor")
    text = text.replace("j Ã¡", "jÃ¡")
    text = text.replace("ecolhidos", "escolhidos")
    text = text.replace("Disfarce l", "Disfarce 1")
    text = text.replace("7pontos", "7 pontos")
    text = text.replace("par ar", "parar")
    text = text.replace("J 202", "1202")
    text = text.replace("Ã  prÃ©mio", "a prÃªmio")
    text = text.replace("prÃ©mio", "prÃªmio")
    text = text.replace("2 Pontos: cantatas.", "2 Pontos: contatos.")
    text = text.replace("2 pontos: 3 pontos de Objetos MÃ¡gicos.", "2 pontos: Objetos MÃ¡gicos.")
    text = text.replace("Alephiapossui", "Alephia possui")
    text = text.replace("22, 5", "22,5")
    text = text.replace("Ã  DoenÃ§as", "a DoenÃ§as")
    text = re.sub(r"\bl (?=(?:ponto|Ponto|PV|Poder|ou 2)\b)", "1 ", text)
    text = re.sub(r"\bl(?=\s+dia\))", "1", text)
    text = re.sub(r"\bl(?=\s*OOKg\b)", "1", text)
    text = re.sub(r"\bl\s*d[lI]\s*[O0]\b", "1d10", text)
    text = re.sub(r"\b2d[lI][O0]\b", "2d10", text)
    text = re.sub(r"\bl\.\s*(\d{3})", r"1.\1", text)
    text = re.sub(r"\blOOkg(s?)\b", r"100kg\1", text)
    text = re.sub(r"(?<=\d)([.,])\s+(?=\d{3}\b)", r"\1", text)
    text = text.replace("1 5,000 AC", "15,000 AC")
    text = re.sub(r"\bl Omin\b", "10 min", text)
    text = text.replace("nfvel", "nível")
    # OCR: l (letra) confundida com 1 (dígito) no início de entradas de custo
    text = text.replace("l ponto:", "1 ponto:")
    text = text.replace("l pontos:", "1 pontos:")

    # 4b. Prefixos de títulos OCR que aparecem colados ao início do parágrafo
    text = re.sub(r'^QuACÃe DG PfiRSONAGfiNS\s*', '', text)
    text = re.sub(r'^QUAC DE PRSONAGENS\s*', '', text)
    text = re.sub(r'^GONcerres BÁsices\s*', '', text)
    text = re.sub(r'^NúmgRes DÊ TBSTE\s*', '', text)
    text = re.sub(r'^CAS ESPECIAL: FffiRCA\s*', '', text)
    text = re.sub(r'^DANS DE ImpAcre\s*', '', text)
    text = re.sub(r'^CeiTIBATE D£SAR\s*', '', text)
    text = re.sub(r'^Teime DE\s*', '', text)
    text = re.sub(r'^A PaimeiRA REBELIÀ\s*', '', text)
    text = re.sub(r'^Os Heaéis G SANTOS\s*', '', text)

    # 5. Confusão numérica adicional
    text = re.sub(r'1d10O\b', '1d100', text)
    text = re.sub(r'\bIdl\s*00\b', '1d100', text)
    text = re.sub(r'chegam a O\b', 'chegam a 0', text)
    text = re.sub(r'\bperde l PV\b', 'perde 1 PV', text)
    text = re.sub(r'\bl Poder\b', '1 Poder', text)
    text = re.sub(r'\blO\s+lados\b', '10 lados', text)
    text = re.sub(r'\b2 37\b', '237', text)

    # 6. Aspas
    text = text.replace('“', '"').replace('”', '"')
    text = text.replace('‘', "'").replace('’', "'")

    # 7. Whitespace e pontuação
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^10\.\s*Pontos de Vida\s+E\s+ÍNDICE DE PROTEÇÃO\.?", "10. Pontos de Vida e Índice de Proteção.", text)
    text = re.sub(r"^11\.\s*SE\?\s*ER\.\s*sNAGem\s*. um IIIAG\.?", "11. Se o Personagem é um Mago.", text)
    text = re.sub(r"^12\.\s*ITENS\s+mÁGices", "12. Itens Mágicos.", text, flags=re.IGNORECASE)
    text = text.replace("Decidimos gastar os pontos de Aprimoramento assim: 2 pontos: 3 pontos de Objetos Mágicos.", "Decidimos gastar os pontos de Aprimoramento assim: 2 pontos em Objetos Mágicos.")
    text = text.replace("Destreza,-Força", "Destreza, Força")
    text = text.replace("Imunidade à Doenças", "Imunidade a Doenças")
    text = text.replace('"sigame"', '"siga-me"')
    text = text.replace("gasto em no Poder", "gasto no Poder")
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text


def merge_fragments(previous: str, current: str) -> str:
    if previous.endswith("-") and current[:1].islower():
        return normalize_text(f"{previous[:-1]}{current}")
    if current.startswith("-") and previous and previous[-1].isalpha():
        return normalize_text(f"{previous}{current[1:]}")
    return normalize_text(f"{previous} {current}")


def should_join(previous: str, current: str) -> bool:
    if not previous or not current:
        return False
    if previous.endswith("-") and current[:1].islower():
        return True
    if current.startswith("-") and previous[-1].isalpha():
        return True
    if current[:1].islower() and not previous.endswith((".", "!", "?", ":", ";", '"')):
        return True
    if len(current) < 65 and current[:1].islower():
        return True
    if previous.endswith(("um", "do", "da", "de", "em", "por", "com", "para")):
        return True
    return False


_DANGLING = frozenset({
    "ao", "à", "a", "o", "os", "as", "de", "do", "da", "dos", "das",
    "em", "no", "na", "nos", "nas", "por", "para", "com", "que", "e",
    "ou", "mas", "um", "uma", "pelo", "pela",
})


def join_lowercase_fragments(paras: list[str]) -> list[str]:
    """Junta paragrafos que iniciam com minuscula ao anterior."""
    result: list[str] = []
    for p in paras:
        if result and p.strip() and p.strip()[0].islower():
            result[-1] = result[-1].rstrip() + " " + p.strip()
        else:
            result.append(p)
    return result


def join_dangling(paras: list[str]) -> list[str]:
    """Junta paragrafos cujo anterior termina com preposicao/artigo."""
    result: list[str] = []
    for p in paras:
        if result:
            words = result[-1].rstrip().split()
            last_word = words[-1].lower().rstrip(".,;:") if words else ""
            if last_word in _DANGLING:
                result[-1] = result[-1].rstrip() + " " + p.strip()
                continue
        result.append(p)
    return result


_OCR_TITLE_NOISE: frozenset[str] = frozenset({
    # Formas corrompidas de títulos OCR que vazam para o corpo do texto
    'QuACÃe DG PfiRSONAGfiNS', 'QUAC DE PRSONAGENS',
    'GONcerres BÁsices', 'NúmgRes DÊ TBSTE',
    'CAS ESPECIAL: FffiRCA', 'DANS DE ImpAcre',
    'CeiTIBATE D£SAR', 'A PfiSTS', 'ReniA E O',
    'Teime DE', 'A PaimeiRA REBELIÀ',
    'Os Heaéis G SANTOS',
    # Formas pós-normalização que ainda podem aparecer
    'QUACE DG PERSONAGENS', 'GONcerres BAsices',
})


def clean_paragraphs(values: Iterable[str]) -> list[str]:
    paragraphs: list[str] = []
    for value in values:
        text = normalize_text(value)
        if not text:
            continue
        # Filtrar títulos OCR corrompidos que vazam para o corpo
        if text in _OCR_TITLE_NOISE:
            continue
        # Ignorar números de página e ruído OCR
        if re.fullmatch(r"P[aá]gina\s+\d+", text):
            continue
        # Filtrar cabeçalhos OCR de seção que aparecem em meio ao texto
        if re.fullmatch(r"PIAN0S\s+DE\s+EXIST[ÊE]NCIA", text):
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?", text):
            continue
        if re.fullmatch(r"\[sem texto reconhecível após a limpeza\]", text):
            continue
        # Filtrar lixo de tabela OCR (diagramacao corrompida)
        if re.search(r"(?:Ativo\s+ffi|IfJ\s+|J-J\s+J|[Ii][~][A-Z][^a-z]{10,})", text):
            continue
        if paragraphs and should_join(paragraphs[-1], text):
            paragraphs[-1] = merge_fragments(paragraphs[-1], text)
        else:
            paragraphs.append(text)
    paragraphs = join_dangling(paragraphs)
    paragraphs = join_lowercase_fragments(paragraphs)
    return paragraphs


def docx_paragraphs() -> list[str]:
    document = Document(SOURCE_PATH)
    return [paragraph.text for paragraph in document.paragraphs]


def section(section_id: str, title: str, area: str, paragraphs: list[str]) -> dict:
    return {
        "id": section_id,
        "title": title,
        "area": area,
        "paragraphs": paragraphs,
    }


def collect(paragraphs: list[str], start: int, end: int) -> list[str]:
    return clean_paragraphs(paragraphs[start:end])


def collect_after_heading(paragraphs: list[str], heading_index: int, end: int) -> list[str]:
    return collect(paragraphs, heading_index + 1, end)


def make_section(paragraphs: list[str], title: str, area: str, start: int, end: int) -> dict:
    return section(slugify(title), title, area, collect_after_heading(paragraphs, start, end))


def make_direct_section(paragraphs: list[str], title: str, area: str, start: int, end: int) -> dict:
    values = collect(paragraphs, start, end)
    title_pattern = re.compile(rf"^{re.escape(title)}\.?\s*", re.IGNORECASE)
    cleaned: list[str] = []
    for value in values:
        next_value = title_pattern.sub("", value, count=1).strip()
        if next_value:
            cleaned.append(next_value)
    return section(slugify(title), title, area, cleaned)


def final_text_cleanup(value: str) -> str:
    replacements = {
        "Ali, nas nuvens. está vendo?": "Ali, nas nuvens, está vendo?",
        "Tetragrammatonah \"": "Tetragrammatonah\"",
        "777falanges": "777 falanges",
        "porque^": "porque",
        "Ê um dos lugares": "É um dos lugares",
        ". E basicamente": ". É basicamente",
        "Magos com Schabour": "Magos como Schabour",
        "OS ÊSTADffiS UNIDffiS": "Os Estados Unidos",
        "ATRIBUTS HIENTAIS": "Atributos Mentais",
        "FORCA DÊ VNTADE": "Força de Vontade",
        "CARISIIIA": "Carisma",
        "PERCEPCAe": "Percepção",
        "VALRÊS oe ATRIBUTS": "Valores de Atributos",
        "ATIVACA DÊ ITENS HlÁcices": "Ativação de Itens Mágicos",
        "O ÇUfi FAZfiR Effl umA RODADA?": "O que fazer em uma rodada?",
        "fllúLTiPiffis ATAQUES": "Múltiplos Ataques",
        "PffiDBRes ÚNices": "Poderes Únicos",
        "ffiUD (somente Principados)": "Fluid (somente Principados)",
        "outra fornia": "outra forma",
        "demora de l a 2 dias": "demora de 1 a 2 dias",
        "INT [ID+ó)": "INT [1D+6]",
        "1D+ó": "1D+6",
        "2D+ó": "2D+6",
        "3D+ó": "3D+6",
        "O anel faz Ido,": "O anel faz 1d6,",
        "possui lOdó cargas": "possui 10d6 cargas",
        "porUrakabarameel": "por Urakabarameel",
        "Grandes génios": "Grandes gênios",
        "Michelângelo": "Michelangelo",
        "DaVinci": "Da Vinci",
        "A ReveLucA INDUSTRIAL": "A Revolução Industrial",
        "AumfiNTe miLAGRese DG ATRIBUTOS": "Aumento Milagroso de Atributos",
        "SUCESSS e FRACASSO AuremÁTices": "Sucessos e Fracassos Automáticos",
        "NancyRoss": "Nancy Ross",
        "AirtonJudah": "Airton Judah",
        "naNormandia": "na Normandia",
        "DesAame O Desarme": "Desarme. O Desarme",
        "TABELA oe OBjeres IIIÁGices:": "Tabela de Objetos Mágicos:",
        "PeoERfis ÚNices": "Poderes Únicos",
        "PeoERes ÚNices": "Poderes Únicos",
        "Peo6R. es ÚNICOS": "Poderes Únicos",
        "DemiNACôes": "Dominações",
        "RfitíPÊRfiS": "Recíperes",
        "NimBus": "Nimbus",
        "BÁsices Atributos": "Básicos. Atributos",
        "Físices": "Atributos Físicos",
        "FORCA (FR)": "Força (FR)",
        "DESTREZA (DfiX)": "Destreza (DEX)",
        "ACUIDADE (AGI)": "Agilidade (AGI)",
        " E importante fixar": " É importante fixar",
        "verificar seu um personagem": "verificar se um personagem",
        "Carro bónus de dano": "Carga. Bônus de dano",
        "prestar atenção, átimo!": "prestar atenção, ótimo!",
        "Joanna D 'Are": "Joanna D'Arc",
        "quer dizer. anjos femininos bem encorpadas. os Portões": "quer dizer, anjos femininos bem encorpados. Os Portões",
        "dela. tempos difíceis": "dela. Tempos difíceis",
        "falar. você conhece": "falar, você conhece",
        "são. como é mesmo o nome. adimensionais": "são, como é mesmo o nome, adimensionais",
        "entre os famoso,": "entre os famosos,",
        "E mais antigo que Júpiter": "É mais antigo que Júpiter",
        "também tem residência": "também têm residência",
        "mantém a ordem": "mantêm a ordem",
        "apost os": "a postos",
        "apostos,": "a postos,",
        "companheiro. aqui está": "companheiro, aqui está",
        "A HisréRiA De PARADÍSIA": "A História de Paradísia",
        "Inferno à servir": "Inferno a servir",
        "15,000 AC": "15.000 AC",
        "Réstia": "Héstia",
        "Metraton": "Metatron",
        "milénios": "milênios",
        "20O anjos": "200 anjos",
        "açõés": "ações",
        "quiserám": "quiseram",
        "explendor": "esplendor",
        "recém chegados": "recém-chegados",
        "entendase": "entenda-se",
        "refugio": "refúgio",
        "pode possui até": "pode possuir até",
        "mago. Já pratica": "mago. Já pratica",
        "11 pontos de Focus": "11 pontos de Focus",
        "1-1 pontos de Focus": "11 pontos de Focus",
        "rod como se fosse": "roda como se fosse",
        "eleja era velho": "ele já era velho",
        "A ÁRven. 6 DA VIDA, A QUABALUA E s SEPHIRAH": "A Árvore da Vida, a Quabalah e os Sephirah",
        "ReniA E O Em 753 AC": "Roma. Em 753 AC",
        "em 1. 118a Ordem": "em 1118, a Ordem",
        "No ano de 1.455": "No ano de 1455",
        "A Am ERIÇA D SUL E CENTRAL": "A América do Sul e Central",
        "TESTE oe PERÍCIA cem": "Teste de Perícia. Da",
        "par a reduzir": "para reduzir",
        "indistritíveis": "indestrutíveis",
        "Nível l:": "Nível 1:",
        "Nível l,": "Nível 1,",
        "Nível l ": "Nível 1 ",
        "Nivel ": "Nível ",
        "Agua Benta": "Água Benta",
        "Imunidade à Venenos": "Imunidade a Venenos",
        "bónus": "bônus",
        "+1 dó": "+1d6",
        "bônus de+1": "bônus de +1",
        "ou-defesa": "ou defesa",
        "norma!": "normal",
        "arrancálo": "arrancá-lo",
        "portal par voltar à terra": "portal para voltar à Terra",
        "sob aponte dos suspiros": "sob a ponte dos suspiros",
        "descobriram* a verdade": "descobriram a verdade",
        "acusandoos de venerar": "acusando-os de venerar",
        "IPlanos de Existêncianglaterra": "Inglaterra",
        "ALEmANHA": "Alemanha",
        "IXfoi": "IX foi",
        "história;, literatura": "história; literatura",
        "(Dite e a Cidade de Ossos)., i -. ' v": "(Dite e a Cidade de Ossos).",
        "feito. em plantas ou animais": "feito em plantas ou animais",
        "Kevin eAndreas": "Kevin e Andreas",
        "FR 16 eAndreas": "FR 16 e Andreas",
        "CONxS metros": "CONx5 metros",
        "açSo": "ação",
        "Chefe Ore": "Chefe Orc",
        " do Ore ": " do Orc ",
        " do Ore é": " do Orc é",
        "O contra-ataque do Ore": "O contra-ataque do Orc",
        "CeiTIBATE DESAR. II! ADe": "Combate Desarmado",
        "III ULTIPl. es OP N ENTES": "Múltiplos Oponentes",
        "Vehue!": "Vehuel",
        "étimos NPCs": "ótimos NPCs",
        "Orbe da Terra. a um preço.": "Orbe da Terra, a um preço.",
        "O Anjo se imune à dor física": "O Anjo se torna imune à dor física",
        "lOPVs": "10 PVs",
        "complexo de ser utilizados": "complexo de ser utilizado",
        "objeto pessoa! apenas": "objeto pessoal apenas",
        "considerase perícia": "considera-se perícia",
        "O NV mUNDO": "O Novo Mundo",
        "VfiLCIDADE": "Velocidade",
        "DANO LecAUZAD": "Dano Localizado",
        "NPCS": "NPCs",
        "Hipnosis": "Hipnose",
        "um pergunta": "uma pergunta",
        "Demónios": "Demônios",
        "gémeos": "gêmeos",
        "bebés": "bebês",
        "colónia": "colônia",
        "colónias": "colônias",
        "aztecas": "astecas",
        "inças": "incas",
        "fenómenos": "fenômenos",
        "Aquilles": "Aquiles",
        "A Origem A criação": "A Origem. A criação",
        "AFASTAR menres -vives": "Afastar Mortos-Vivos.",
        "ser á feito": "será feito",
        "fenómeno": "fenômeno",
        "fenómenos": "fenômenos",
        "15,000 anos": "15.000 anos",
        "afinesse": "a finesse",
        "sensibilidade afetivarara": "sensibilidade afetiva rara",
        "Estes X dó são rolados": "Estes X dados são rolados",
        "Fogo, Água, Terra. Ar": "Fogo, Água, Terra, Ar",
        "voar a a até": "voar a até",
        "deve se testar PER": "deve-se testar PER",
        "teste de CAR Não": "teste de CAR. Não",
        "hipnotisar": "hipnotizar",
        "espera os pontos retomarem": "espera os pontos retornarem",
        "portais da terra": "portais da Terra",
        "dá a que o utilizar": "dá a quem o utilizar",
        "p/ escapar": "para escapar",
        "página 1 8": "página 18",
        "O mais provável é que. nenhum": "O mais provável é que nenhum",
        "Isto o ajudará e entender": "Isto o ajudará a entender",
        "Adverso Se combate": "Adverso. Se o combate",
        "trate as cada uma separadamente": "trate cada uma separadamente",
        "O dano é 1d6 a cada por metro de queda": "O dano é 1d6 a cada metro de queda",
        "reduz o dano em \\ dó": "reduz o dano em 1d6",
        "uma único parte": "uma única parte",
        "As chances do Orc acenar": "As chances do Orc acertar",
        "Dominações São": "Dominações. São",
        "lerathel": "Ierathel",
        "inflingir": "infligir",
        "NÃO tem direito": "NÃO têm direito",
        "Pessoas observadas tem": "Pessoas observadas têm",
        "Guerra entre Católicos, Judeus e Muçulmanos têm acirrado": "Guerra entre Católicos, Judeus e Muçulmanos tem acirrado",
        "Ire! É também": "Ih! É também",
        "anjos gostosíssimas": "anjas gostosíssimas",
        "O Solarium Em algum lugar": "O Solarium. Em algum lugar",
        "altíssimos, e fora": "altíssimos, é fora",
        "Olympus Os dois": "Olympus. Os dois",
        "As Pirâmides Após": "As Pirâmides. Após",
        "A GUERRA oes cem AHOS": "A Guerra dos Cem Anos.",
        "A Peste Em": "A Peste. Em",
        "A GUERRA DAS DUAS RSAS": "A Guerra das Duas Rosas",
        "A PCNÍNSULA IBÉRICA": "A Península Ibérica",
        "A CACA ÀS BRUXAS": "A Caça às Bruxas",
        "A ÁPRICA": "A África",
        "O SÉCUL XXI": "O Século XXI",
        "PASS": "Passo 1",
        "Não dejesar": "Não desejar",
        "Objetívos": "Objetivos",
        "LISTA Dg PERÍCIAS BÁSICAS": "Lista de Perícias Básicas",
        "NVAS PERÍCIAS": "Novas Perícias",
        "PNTOS D6": "Pontos de Fé",
        "Aumente DE ATRIBUTOS": "Aumento de Atributos",
        "Aumento de Atributos Atributos Físicos": "Aumento de Atributos Físicos.",
        "CONTROLAR HIORTOS-Vivos": "Controlar Mortos-Vivos",
        "'TESTE DE ATRIBUT": "Teste de Atributo",
        "ATRIBUT vs. ATRIBUT": "Atributo vs. Atributo",
        "PERÍCIA vs. ATRIBUT": "Perícia vs. Atributo",
        "Somando Atributos É": "Somando Atributos. É",
        "[Artes - Pintura 45J": "[Artes - Pintura 45]",
        "l - INTENÇÕES": "1 - Intenções",
        "3H ATAQUES eu ACÔES": "3 - Ataques ou Ações",
        "com as mão": "com as mãos",
        "DAM": "Dano",
        "ATAQUE LQCAUZAD": "Ataque Localizado",
        "ATAQUE TTAL": "Ataque Total",
        "DEFESA TTAL": "Defesa Total",
        "PesicA DESVANTAJOSA": "Posição Desvantajosa",
        "Combate Mortal Dois": "Combate Mortal. Dois",
        "10 P V": "10 PV",
        "Quedas Existem": "Quedas. Existem",
        "cotação diferentes": "cotação diferente",
        "gigantes. todas tem": "gigantes, todas têm",
        "mercado e. podem variar": "mercado, e podem variar",
        "outro. basta": "outro; basta",
        "presença se seres": "presença de seres",
        "ambidesíria": "ambidestria",
        "A. origem": "A origem",
        "Cataluny a": "Catalunha",
        "três mans (mãos)": "três mãos",
        "Somavam cerca 5%": "Somavam cerca de 5%",
        "Armas Espada longa Espada de fogo Lança Rede Arco e flecha Crítico Dano 1d8+3 2d6+3 2d6+3 Especial Para as perícias comuns": "Para as perícias comuns",
        "oulro lado": "outro lado",
        "roda em que vai atacar": "rodada em que vai atacar",
        "não poder ser atacado": "não pode ser atacado",
        "apenalidade": "a penalidade",
        "dívida o resultado": "divida o resultado",
        "Desaçõeselhamos": "Desaconselhamos",
        "Pontos Heróicos": "Pontos Heroicos",
        ". Fluid (somente Principados)": ".",
        "recebidos como herança de seu mentor, roubados de um outro mago, anjo ou demônio ou mesmo criado por ele mesmo": "recebida como herança de seu mentor, roubada de um outro mago, anjo ou demônio ou mesmo criada por ele mesmo",
        "E pode consultar esta biblioteca": "Ele pode consultar esta biblioteca",
        "Também podem ajudá-lo em pesquisas": "Também pode ajudá-lo em pesquisas",
    }
    for before, after in replacements.items():
        value = value.replace(before, after)
    value = value.replace("mãoss", "mãos")
    value = value.replace("Desaçõeselhamos", "Desaconselhamos")
    value = re.sub(r"prestar aten[cç][aã]o,\s*[áa]timo!", "prestar atenção, ótimo!", value, flags=re.IGNORECASE)
    value = re.sub(r"Joanna D\s*'\s*Are", "Joanna D'Arc", value)
    value = re.sub(r"quer dizer\.\s+anjos femininos bem encorpadas\.\s+os Portões", "quer dizer, anjos femininos bem encorpados. Os Portões", value)
    value = re.sub(r"s[ãa]o\.\s+como é mesmo o nome\.\s+adimensionais", "são, como é mesmo o nome, adimensionais", value)
    value = re.sub(r"entre os famoso\b", "entre os famosos", value)
    value = re.sub(r"\bE mais antigo que Júpiter", "É mais antigo que Júpiter", value)
    value = re.sub(r"Metraton", "Metatron", value)
    value = re.sub(r"A Hisr.RiA De PARAD.SIA", "A História de Paradísia", value)
    value = re.sub(r"\bmil[eé]nios\b", "milênios", value)
    value = re.sub(r"\b20O anjos\b", "200 anjos", value)
    value = re.sub(r"a[cç][õo].s", "ações", value)
    value = re.sub(r"quiser.m", "quiseram", value)
    value = re.sub(r"explendor", "esplendor", value)
    value = re.sub(r"rec[eé]m chegados", "recém-chegados", value)
    value = re.sub(r"entendase", "entenda-se", value)
    value = re.sub(r"\brefugio\b", "refúgio", value)
    value = re.sub(r"pode possui(?!r)\b", "pode possuir", value)
    value = re.sub(r"possuirr\b", "possuir", value)
    value = re.sub(r"1-1 pontos de Focus", "11 pontos de Focus", value)
    value = re.sub(r"\bDesa\w*elhamos\b", "Desaconselhamos", value)
    value = re.sub(r"\bNivel\b", "Nível", value)
    value = re.sub(r"\bNível\s+l\b", "Nível 1", value)
    value = re.sub(r"\bl a (?=\d+\b)", "1 a ", value)
    value = re.sub(r"\bem 1\.(\d{3})\b", r"em 1\1", value)
    value = value.replace("Imunidade à Doenças", "Imunidade a Doenças")
    value = value.replace('"sigame"', '"siga-me"')
    value = value.replace("gasto em no Poder", "gasto no Poder")
    value = value.replace("Destreza,-Força", "Destreza, Força")
    return value


def cleanup_payload(value):
    if isinstance(value, str):
        return final_text_cleanup(value)
    if isinstance(value, list):
        return [cleanup_payload(item) for item in value]
    if isinstance(value, dict):
        return {key: cleanup_payload(item) for key, item in value.items()}
    return value


def split_power(title: str, paragraphs: list[str]) -> dict:
    prereq: list[str] = []
    body = list(paragraphs)
    inline_heading = re.compile(rf"^{re.escape(title.replace(' (Poder)', ''))}\s*\(([^)]+)\)\s*(.*)$", re.IGNORECASE)
    if body:
        match = inline_heading.match(body[0])
        if match:
            prereq.append(match.group(1).strip())
            if match.group(2).strip():
                body[0] = match.group(2).strip()
            else:
                body.pop(0)
    # First line in parentheses = casta restriction / prerequisite
    if body and re.fullmatch(r"\(.+\)", body[0]):
        prereq.append(body.pop(0).strip("()"))
    elif body:
        first = body[0].strip()
        match = re.match(r"^\(([^)]+)\)\s*(.*)$", first)
        if match:
            prereq.append(match.group(1).strip())
            if match.group(2).strip():
                body[0] = match.group(2).strip()
            else:
                body.pop(0)
    default_prereq = {
        "Bênção": "todas as castas",
        "Combate": "somente Protetores e Captares",
        "Comunhão": "todas as castas",
        "Controle Mental": "todas as castas",
        "Defesas": "todas as castas",
        "Defesas Especiais": "todas as castas",
        "Disfarces": "todas as castas",
        "Dreno": "somente Recíperes",
        "Energização": "todas as castas",
        "Gupe": "todas as castas",
        "Lextaliems": "somente Dominações",
        "Mensageiro Celestial": "somente Protetores",
        "Nimbus (Poder)": "somente Nimbus",
        "Passagem Astral": "somente Corpore",
        "Percepção Divina": "somente Virtudes",
        "Querubia": "somente Querubins",
        "Principados (Poder)": "somente Principados",
        "Regeneração": "todas as castas",
        "Simulacro": "todas as castas",
        "Telecinesia": "todas as castas",
    }
    if not prereq and title in default_prereq:
        prereq.append(default_prereq[title])

    text = " ".join(body)
    text = re.sub(r"\bNivel\b", "Nível", text)
    text = re.sub(r"(?i)\bN[íi]vel\s+l\b", "Nível 1", text)
    marker = re.compile(r"(?i)\bN[íi]vel\s+(\d+|X):\s*")
    matches = list(marker.finditer(text))

    sections = []
    if prereq:
        sections.append(section("pre-requisito", "Pré-requisito", "poderes", prereq))

    if matches:
        for index, match in enumerate(matches):
            level = match.group(1)
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            content = normalize_text(text[start:end])
            if not content:
                continue
            sections.append(section(f"nivel-{level}-{index + 1}", f"Nível {level}", "poderes", [content]))
    elif body:
        sections.append(section("descricao", "Descrição", "poderes", body))

    summary_paragraphs = [paragraph for item in sections for paragraph in item.get("paragraphs", [])]

    return {
        "id": slugify(title),
        "title": title,
        "area": "poderes",
        "kind": "power",
        "sectionId": "poder",
        "sectionTitle": "Poder",
        "paragraphs": summary_paragraphs,
        "sections": sections,
    }


def split_attribute_power(paragraphs: list[str]) -> dict:
    sections = [section("pre-requisito", "Pré-requisito", "poderes", ["todas as castas"])]
    intro: list[str] = []
    variants: list[str] = []
    current: str | None = None
    marker = re.compile(r"^(Força|Constituição|Destreza|Agilidade|Inteligência|Força de Vontade|Carisma|Percepção):\s*(.*)$")
    for paragraph in paragraphs:
        text = normalize_text(paragraph)
        text = re.sub(r"^Aumento de Atributos\s+\(todas as castas\)\s*", "", text, flags=re.IGNORECASE)
        if text.startswith("(todas as castas)"):
            text = text.removeprefix("(todas as castas)").strip()
        match = marker.match(text)
        if match:
            if current:
                variants.append(current)
            current = f"{match.group(1)}: {match.group(2)}".strip()
        elif current:
            current = normalize_text(f"{current} {text}")
        else:
            intro.append(text)
    if current:
        variants.append(current)
    if intro:
        sections.append(section("descricao", "Descrição", "poderes", intro))
    for index, variant in enumerate(variants, start=1):
        name = variant.split(":", 1)[0]
        sections.append(section(f"variante-{index}", name, "poderes", [variant]))
    summary_paragraphs = [paragraph for item in sections for paragraph in item.get("paragraphs", [])]
    return {
        "id": "aumento-de-atributos",
        "title": "Aumento de Atributos",
        "area": "poderes",
        "kind": "power",
        "sectionId": "poder",
        "sectionTitle": "Poder",
        "paragraphs": summary_paragraphs,
        "sections": sections,
    }


def split_enhancement(title: str, paragraphs: list[str]) -> dict:
    cost_entries: list[dict] = []
    cost_effects: list[str] = []
    cost_pattern = re.compile(
        r"(?i)\b(\d+\s+pontos?(?:\s+(?:por|para)\s+[^:]{1,40})?|pontos?|ponto|pactos\s+[—-]\s+variável|variável):\s*"
    )
    inferred_cost = 1
    text = normalize_text(" ".join(paragraphs))
    text = re.sub(rf"^{re.escape(title)}\s+", "", text, flags=re.IGNORECASE)
    matches = list(cost_pattern.finditer(text))

    if matches:
        description = normalize_text(text[: matches[0].start()])
        for index, match in enumerate(matches):
            label = match.group(1)
            if re.search(r"(?i)pactos\s+[—-]\s+variável|^variável$", label):
                label = "Variável"
            label_key = label.casefold().strip()
            explicit_number = re.match(r"(\d+)", label_key)
            if explicit_number:
                inferred_cost = max(inferred_cost, int(explicit_number.group(1)) + 1)
            elif label_key in {"ponto", "pontos"}:
                label = f"{inferred_cost} {'ponto' if inferred_cost == 1 else 'pontos'}"
                inferred_cost += 1
            next_start = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            effect = text[match.end():next_start].strip()
            cost_entries.append({"label": normalize_text(label), "effect": normalize_text(effect)})
            if effect:
                cost_effects.append(normalize_text(effect))
    else:
        description = text

    sections = []
    if cost_entries:
        cost_paragraphs = [
            entry["label"] if len(cost_entries) == 1 or not entry["effect"]
            else f"{entry['label']}: {entry['effect']}"
            for entry in cost_entries
        ]
        sections.append(section("custo", "Custo", "aprimoramentos", cost_paragraphs))
    if len(cost_entries) == 1:
        description_text = normalize_text(" ".join(part for part in [description, *cost_effects] if part))
    else:
        description_text = normalize_text(description or " ".join(cost_effects) or text)
    sections.append(
        section("descricao", "Descrição", "aprimoramentos", [description_text] if description_text else [])
    )

    return {
        "id": slugify(title),
        "title": title,
        "area": "aprimoramentos",
        "kind": "enhancement",
        "sectionId": "descricao",
        "sectionTitle": "Aprimoramento",
        "paragraphs": paragraphs,
        "sections": sections,
    }


def split_equipment(paragraphs: list[str]) -> tuple[list[dict], list[dict]]:
    intro = paragraphs[:11]
    item_paragraphs = paragraphs[11:102]
    outro = paragraphs[102:]
    intro_sections = [
        section("observacoes", "Observações", "itens_equipamentos", intro),
    ]
    if outro:
        intro_sections.append(section("criacao-de-itens", "Criando Seus Próprios Itens Mágicos", "itens_equipamentos", outro))

    items: list[dict] = []
    current: dict | None = None
    title_pattern = re.compile(r"^([^:]{2,90}):\s*(.*)$")
    expanded_paragraphs: list[str] = []
    for paragraph in item_paragraphs:
        expanded_paragraphs.extend(re.sub(r"\s+(Anel de Tyr:)", r"\n\1", paragraph).splitlines())

    used_ids: dict[str, int] = {}
    for paragraph in expanded_paragraphs:
        text = normalize_text(paragraph)
        text = re.sub(r"^I\s+(Armadura\s+\+\d)", r"\1", text)
        match = title_pattern.match(text)
        if match:
            if current:
                items.append(current)
            title = normalize_text(match.group(1))
            body = normalize_text(match.group(2))
            base_id = f"anjos-item-{slugify(title)}"
            used_ids[base_id] = used_ids.get(base_id, 0) + 1
            item_id = base_id if used_ids[base_id] == 1 else f"{base_id}-{used_ids[base_id]}"
            current = {
                "id": item_id,
                "title": title,
                "area": "itens_equipamentos",
                "kind": "equipment",
                "sectionId": "descricao",
                "sectionTitle": "Item",
                "paragraphs": [body] if body else [],
                "sections": [section("descricao", "Descrição", "itens_equipamentos", [body] if body else [])],
            }
        elif current:
            current["paragraphs"].append(text)
            current["sections"][0]["paragraphs"].append(text)
        else:
            intro_sections[0]["paragraphs"].append(text)
    if current:
        items.append(current)
    return intro_sections, items


def build_pilot() -> dict:
    paragraphs = docx_paragraphs()

    # ── LORE ─────────────────────────────────────────────────────────────────
    # Introdução (62–68), Conceitos Básicos (76–126), A Cidade de Prata (126–133)
    # Distritos: Luna(133–164), Vênus(164–168), Marte(168–181), Júpiter(181–194)
    # Política (194–206), A História de Paradísia (206–228)
    # Planos de Existência (228–261)
    # Cidades: Olympus/Ra/Aasgard/Kabbalah/Katmaran (240–261)
    # As Terras / Hermes / Guerra de Tróia / Nascimento de Jesus / Expansão (261–395)
    lore_sections = [
        make_section(paragraphs, "Introdução", "cenarios_lore", 62, 68),
        make_section(paragraphs, "A Cidade de Prata", "cenarios_lore", 126, 133),
        make_section(paragraphs, "Luna", "cenarios_lore", 133, 164),
        make_section(paragraphs, "Vênus", "cenarios_lore", 164, 168),
        make_section(paragraphs, "Marte", "cenarios_lore", 168, 181),
        make_section(paragraphs, "Júpiter", "cenarios_lore", 181, 194),
        make_section(paragraphs, "A Política na Cidade de Prata", "cenarios_lore", 194, 206),
        make_direct_section(paragraphs, "A História de Paradísia", "cenarios_lore", 206, 232),
        make_section(paragraphs, "Planos de Existência", "cenarios_lore", 232, 261),
        make_section(paragraphs, "As Terras — Hermes e a Segunda Rebelião", "cenarios_lore", 261, 281),
        make_section(paragraphs, "A Guerra de Tróia", "cenarios_lore", 281, 294),
        make_section(paragraphs, "Nascimento de Jesus", "cenarios_lore", 294, 299),
        make_section(paragraphs, "A Expansão da Cidade de Prata", "cenarios_lore", 299, 395),
        make_section(paragraphs, "Criando Sua Própria Cidade de Anjos", "cenarios_lore", 1732, 1752),
    ]

    # ── REGRAS ────────────────────────────────────────────────────────────────
    # Criação de Personagens (413–553), Atributos (779–823), Perícias (823–893)
    # Pontos de Fé (1379–1422), Regras e Testes (1422–1752)
    rules_sections = [
        make_direct_section(paragraphs, "Conceitos Básicos", "regras_base", 76, 126),
        make_direct_section(paragraphs, "Criação de Personagens", "regras_base", 413, 414),
        make_section(paragraphs, "1. Escolha a Campanha", "regras_base", 414, 426),
        make_direct_section(paragraphs, "2. Escolha uma História Mortal", "regras_base", 426, 486),
        make_direct_section(paragraphs, "3. Verifique Detalhes da História", "regras_base", 486, 491),
        make_direct_section(paragraphs, "4. Datas, Locais e Casta", "regras_base", 491, 495),
        make_direct_section(paragraphs, "5. Escolha seus Atributos", "regras_base", 495, 504),
        make_direct_section(paragraphs, "6. Escolha os Poderes Angelicais", "regras_base", 504, 507),
        make_direct_section(paragraphs, "7. Escolha os Aprimoramentos", "regras_base", 507, 516),
        make_direct_section(paragraphs, "8. Escolha os Inimigos de Personagem", "regras_base", 516, 525),
        make_direct_section(paragraphs, "9. Perícias com Armas e Perícias Comuns", "regras_base", 525, 535),
        make_direct_section(paragraphs, "10. Pontos de Vida e Índice de Proteção", "regras_base", 535, 540),
        make_direct_section(paragraphs, "11. Se o Personagem é um Mago", "regras_base", 540, 547),
        make_direct_section(paragraphs, "12. Itens Mágicos", "regras_base", 547, 548),
        make_section(paragraphs, "13. Reunindo os Personagens", "regras_base", 548, 553),
        make_direct_section(paragraphs, "Atributos", "regras_base", 779, 823),
        make_direct_section(paragraphs, "Perícias", "regras_base", 823, 893),
        make_direct_section(paragraphs, "Pontos de Fé", "regras_base", 1379, 1422),
        make_section(paragraphs, "Regras e Testes", "regras_base", 1422, 1732),
    ]

    # ── CLASSES / HIERARQUIAS ────────────────────────────────────────────────
    # Corpore (553–666), Protetores intro+subcastas (589–710),
    # Captare (666–710), Recíperes (703–746), Nimbus (741–779)
    # Subcastas dos Protetores: Querubins(593–617), Potências(617–626),
    #   Virtudes(626–637), Principados(637–657), Seráfins(657–666)
    class_sections = [
        make_section(paragraphs, "Corpore", "classes", 553, 593),
        make_section(paragraphs, "Querubins", "classes", 593, 617),
        make_section(paragraphs, "Potências", "classes", 617, 626),
        make_section(paragraphs, "Virtudes", "classes", 626, 637),
        make_section(paragraphs, "Principados", "classes", 637, 657),
        make_section(paragraphs, "Seráfins", "classes", 657, 666),
        make_section(paragraphs, "Captare", "classes", 666, 710),
        make_section(paragraphs, "Recíperes", "classes", 703, 746),
        make_section(paragraphs, "Nimbus", "classes", 741, 779),
    ]

    # ── PODERES ANGELICAIS ────────────────────────────────────────────────────
    # Seção principal: 975–1265
    # Poderes identificados por "Título OCR" e por padrão de nome+parênteses:
    power_ranges = [
        ("Aumento de Atributos", 980, 991),
        ("Asas Astrais", 991, 1000),
        ("Bard", 1000, 1014),
        ("Bênção", 1014, 1025),
        ("Captare (Poder)", 1025, 1038),
        ("Combate", 1038, 1044),
        ("Comunhão", 1044, 1048),
        ("Controle Mental", 1048, 1076),
        ("Defesas", 1076, 1085),
        ("Defesas Especiais", 1085, 1100),
        ("Disfarces", 1100, 1105),
        ("Dreno", 1105, 1119),
        ("Druidia", 1119, 1135),
        ("Energização", 1135, 1146),
        ("Principados (Poder)", 1146, 1157),
        ("Gupe", 1157, 1167),
        ("Lextaliems", 1167, 1176),
        ("Mensageiro Celestial", 1176, 1190),
        ("Nimbus (Poder)", 1190, 1208),
        ("Passagem Astral", 1208, 1219),
        ("Percepção Divina", 1219, 1230),
        ("Querubia", 1230, 1245),
        ("Regeneração", 1245, 1254),
        ("Simulacro", 1254, 1259),
        ("Telecinesia", 1259, 1267),
    ]
    power_sections = []
    direct_power_titles = {"Comunhão", "Gupe", "Regeneração", "Simulacro"}
    for title, start, end in power_ranges:
        if title == "Aumento de Atributos":
            power_sections.append(split_attribute_power(collect(paragraphs, start, end)))
        elif title == "Principados (Poder)":
            power_sections.append(split_power(title, collect(paragraphs, start, end)))
        elif title in direct_power_titles:
            power_sections.append(split_power(title, collect(paragraphs, start, end)))
        else:
            power_sections.append(split_power(title, collect_after_heading(paragraphs, start, end)))

    # ── APRIMORAMENTOS ────────────────────────────────────────────────────────
    # 893–975: lista de aprimoramentos identificados por Título OCR
    # Nota: Biblioteca Arcana (904-909) e Clérigo (909-918) são entradas separadas no livro;
    #   Local de Controle (929-931), Objetos Mágicos (931) e Pactos (932-934) idem;
    #   Pertencer ou Comandar uma Seita (940-942) e Poderes Mágicos (942-950) idem.
    enhancement_ranges = [
        ("Afinidade com Fadas", 893, 899),
        ("Alma Dupla", 899, 902),
        ("Ambidestria", 902, 904),
        ("Biblioteca Arcana", 904, 909),
        ("Clérigo", 909, 918),
        ("Detecção de Magia", 918, 921),
        ("Gárgula", 921, 926),
        ("Guardião de um Artefato Importante", 926, 929),
        ("Local de Controle", 929, 931),
        ("Objetos Mágicos", 930, 932),
        ("Pactos", 931, 934),
        ("Palavra de Deus", 934, 936),
        ("Pertencer a uma Escola de Magia", 936, 940),
        ("Pertencer ou Comandar uma Seita", 940, 942),
        ("Poderes Mágicos", 942, 950),
        ("Sensitivo", 950, 956),
        ("Senso de Direção", 956, 958),
        ("Senso", 958, 960),
        ("Sentidos Aguçados", 960, 962),
        ("Sortudo", 962, 964),
        ("Talento", 964, 966),
        ("Tutor", 966, 975),
    ]
    enhancement_sections = []
    for title, start, end in enhancement_ranges:
        values = collect(paragraphs, start, end) if title == "Alma Dupla" else collect_after_heading(paragraphs, start, end)
        enhancement_sections.append(split_enhancement(title, values))

    # ── ITENS MÁGICOS ─────────────────────────────────────────────────────────
    # 1267–1379: tabela de objetos mágicos (bloco único + regras de criação)
    equipment_sections, equipment_items = split_equipment(collect(paragraphs, 1267, 1379))

    # ── GRUPOS ───────────────────────────────────────────────────────────────
    groups = [
        {
            "id": "anjos-cidade-prata-lore",
            "title": "Anjos — A Cidade de Prata",
            "kind": "setting",
            "area": "cenarios_lore",
            "sectionTitle": "Cenário",
            "sections": lore_sections,
        },
        {
            "id": "anjos-regras",
            "title": "Regra base - Anjos - A Cidade de Prata",
            "kind": "ruleset",
            "area": "regras_base",
            "sectionTitle": "Regra Base",
            "sections": rules_sections,
        },
        {
            "id": "anjos-objetos-magicos",
            "title": "Objetos Mágicos",
            "kind": "equipment_group",
            "area": "itens_equipamentos",
            "sectionTitle": "Itens e Equipamentos",
            "sections": equipment_sections,
        },
    ]

    sections = class_sections + power_sections + enhancement_sections + equipment_items

    area_counts: dict[str, int] = {}
    for group in groups:
        area_counts[group["area"]] = area_counts.get(group["area"], 0) + 1
    for item in sections:
        area_counts[item["area"]] = area_counts.get(item["area"], 0) + 1

    return {
        "version": 1,
        "status": "pilot_review",
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "source": SOURCE,
        "sourceFile": SOURCE_PATH.name,
        "sourcePath": str(SOURCE_PATH.relative_to(ROOT)).replace("\\", "/"),
        "title": "Anjos - A Cidade de Prata",
        "summary": (
            "Suplemento sobre anjos no universo Daemon/Trevas. "
            "Apresenta a Cidade de Prata (Paradísia), seus seis distritos, cinco castas angelicais "
            "(Corpore, Protetores, Captare, Recíperes, Nimbus), poderes angelicais por hierarquia, "
            "aprimoramentos, objetos mágicos, regras de criação de personagem e testes."
        ),
        "areas": sorted(area_counts),
        "groups": groups,
        "sections": sections,
        "areaCounts": area_counts,
        "reviewNotes": [
            "Piloto gerado por faixas de índice do DOCX OCR.",
            "Títulos OCR têm ruído significativo — nomes de poderes e seções devem ser revisados manualmente.",
            "Subcastas dos Protetores (Querubins, Potências, Virtudes, Principados, Seráfins, Anjos/Arcanjos) modeladas como classes individuais.",
            "Poderes únicos por casta estão dentro do capítulo de Poderes Angelicais (975–1265) — mapeados individualmente.",
            "Aprimoramentos (893–975): sem títulos de Nível 1/2/3, usam 'N pontos:' — split_enhancement aplicado.",
            "Itens mágicos agrupados em bloco único (1267–1379) — revisão item a item recomendada.",
            "NPCs de Barcelona mencionados na seção 'Criando Sua Própria Cidade de Anjos' (1732+) — não há fichas estruturadas no DOCX.",
            "Seção 'Lanças de Christos' e 'Anjos Principais' (57–59 no índice) não localizada no corpo do texto — possível corte na OCR.",
        ],
    }


def main() -> None:
    payload = cleanup_payload(build_pilot())
    write_json(OUT_PATH, payload)
    write_json(DOCS_OUT_PATH, payload)
    print(
        json.dumps(
            {
                "source": payload["source"],
                "groups": len(payload["groups"]),
                "sections": len(payload["sections"]),
                "areas": payload["areaCounts"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
