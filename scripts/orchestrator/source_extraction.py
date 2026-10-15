"""Read-only extraction evidence. XML locations are never invented book pages."""
from __future__ import annotations

from collections import Counter
import hashlib
import io
from pathlib import Path
import unicodedata
import xml.etree.ElementTree as ET
import zipfile

from scripts.agents.application_runtime import ResourceBounds

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
LIGATURES = {chr(code): unicodedata.normalize("NFKC", chr(code)) for code in range(0xFB00, 0xFB07)}
MAX_XML_BYTES = 64 * 1024 * 1024
MAX_BLOCKS = 100_000
MAX_PAGES = 10_000
NORMALIZATION_VERSION = f"unicode-ligatures-1/{unicodedata.unidata_version}"


def text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_text(text: str) -> tuple[str, dict[str, int]]:
    """Only Unicode presentation ligatures. Keep numbers, hard hyphens and spacing."""
    corrections = {char: text.count(char) for char in LIGATURES if char in text}
    for char, replacement in LIGATURES.items():
        text = text.replace(char, replacement)
    return text, corrections


def _block(anchor: str, raw: str, *, kind: str, part: str, page: int | None,
           tokens: list[dict] | None = None) -> dict:
    clean, changes = normalize_text(raw)
    return {"anchor": anchor, "kind": kind, "part": part, "page": page,
            "rawText": raw, "cleanText": clean, "rawTextSha256": text_hash(raw),
            "cleanTextSha256": text_hash(clean), "normalizations": changes,
            "auxiliaryTokens": tokens or []}


def _docx(raw: bytes) -> dict:
    blocks = []
    text_nodes = 0
    extracted_nodes = 0
    table_count = 0
    hints = Counter()
    parts = []
    flags = set()
    with zipfile.ZipFile(io.BytesIO(raw)) as package:
        names = package.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate DOCX package members are ambiguous")
        if "word/document.xml" not in names:
            raise ValueError("DOCX main document part is missing")
        xml_infos = [item for item in package.infolist() if item.filename.endswith(".xml")]
        if len(xml_infos) > 1024 or sum(item.file_size for item in xml_infos) > MAX_XML_BYTES:
            raise ValueError("DOCX XML resource limit exceeded")
        media_count = sum(name.startswith("word/media/") for name in names)
        embedded_count = sum(name.startswith("word/embeddings/") for name in names)
        if media_count:
            flags.add("VISUAL_CONTENT_REQUIRES_REVIEW")
        if embedded_count:
            flags.add("EMBEDDED_CONTENT_REQUIRES_REVIEW")
        story_names = sorted(name for name in names if name.startswith("word/") and name.endswith(".xml"))
        story_names.sort(key=lambda name: name != "word/document.xml")
        for name in story_names:
            xml = package.read(name)
            if b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:
                raise ValueError("DTD/entity declarations are not supported")
            root = ET.fromstring(xml)
            if not any(node.tag in (W + "p", W + "t") for node in root.iter()):
                continue
            parts.append({"path": name, "sha256": hashlib.sha256(xml).hexdigest()})
            parent = {child: element for element in root.iter() for child in element}
            paths = {root: "/" + root.tag.rsplit("}", 1)[-1] + "[1]"}
            for element in root.iter():
                counts = Counter()
                for child in element:
                    counts[child.tag] += 1
                    paths[child] = paths[element] + "/" + child.tag.rsplit("}", 1)[-1] + f"[{counts[child.tag]}]"
            paragraphs = [element for element in root.iter() if element.tag == W + "p"]
            consumed = set()
            for paragraph in paragraphs:
                segments = []
                auxiliary = []

                def collect(element):
                    if element is not paragraph and element.tag == W + "p":
                        return  # Nested textboxes have their own anchored paragraph.
                    if element.tag == W + "t":
                        segments.append(element.text or "")
                        consumed.add(element)
                    elif element.tag == W + "tab":
                        segments.append("\t")
                    elif element.tag in (W + "br", W + "cr"):
                        segments.append("\n")
                    elif element.tag == W + "noBreakHyphen":
                        segments.append("\u2011")
                    elif element.tag == W + "softHyphen":
                        segments.append("\u00ad")
                    elif element.tag in (W + "instrText", W + "delText"):
                        auxiliary.append({"kind": element.tag.rsplit("}", 1)[-1],
                                          "text": element.text or "", "anchor": name + "#" + paths[element]})
                    for child in element:
                        collect(child)
                collect(paragraph)
                ancestor = parent.get(paragraph)
                in_table = False
                while ancestor is not None:
                    in_table = in_table or ancestor.tag == W + "tc"
                    ancestor = parent.get(ancestor)
                blocks.append(_block(name + "#" + paths[paragraph], "".join(segments),
                                     kind="table_paragraph" if in_table else "paragraph",
                                     part=name, page=None, tokens=auxiliary))
            # Preserve unusual word text outside a paragraph rather than silently dropping it.
            for element in root.iter(W + "t"):
                text_nodes += 1
                if element not in consumed:
                    blocks.append(_block(name + "#" + paths[element], element.text or "",
                                         kind="orphan_text", part=name, page=None))
                    flags.add("ORPHAN_TEXT_REQUIRES_REVIEW")
                extracted_nodes += 1
            for element in root.iter():
                if element.tag == W + "tbl":
                    table_count += 1
                if element.tag == W + "lastRenderedPageBreak":
                    hints["renderedBreakCount"] += 1
                if element.tag == W + "br" and element.get(W + "type") == "page":
                    hints["explicitBreakCount"] += 1
                if element.tag in (W + "ins", W + "del"):
                    flags.add("TRACKED_CHANGES_REQUIRE_REVIEW")
                if element.tag in (W + "altChunk", W + "txbxContent") or element.tag.endswith("}AlternateContent"):
                    flags.add("COMPLEX_LAYOUT_REQUIRES_REVIEW")
            if len(blocks) > MAX_BLOCKS:
                raise ValueError("Extracted block resource limit exceeded")
    flags.add("SOURCE_PAGE_MAPPING_REQUIRED")
    return {"format": "docx", "pageBasis": "UNVERIFIED", "pageCount": None,
            "blocks": blocks, "parts": parts, "tableCount": table_count,
            "mediaPartCount": media_count, "embeddedPartCount": embedded_count,
            "pageHints": dict(sorted(hints.items())),
            "coverage": {"wordTextNodeCount": text_nodes, "extractedWordTextNodeCount": extracted_nodes},
            "issueCodes": sorted(flags)}


def _pdf(raw: bytes) -> dict:
    import fitz

    blocks = []
    visual_pages = []
    with fitz.open(stream=raw, filetype="pdf") as document:
        if document.needs_pass:
            raise ValueError("Encrypted PDF needs an explicitly configured reader")
        if document.page_count > MAX_PAGES:
            raise ValueError("PDF page resource limit exceeded")
        for index, page in enumerate(document, 1):
            # Physical PDF page index is evidence; printed page labels are not inferred.
            blocks.append(_block(f"pdf:page:{index}", page.get_text("text", sort=False),
                                 kind="page", part="pdf", page=index))
            drawings = page.get_drawings()
            images = page.get_images()
            if images or drawings or page.annots() is not None or page.widgets() is not None:
                # annots/widgets return iterators even when empty in some PyMuPDF releases.
                if images or drawings or list(page.annots() or ()) or list(page.widgets() or ()):
                    visual_pages.append(index)
        count = document.page_count
    return {"format": "pdf", "pageBasis": "PDF_PHYSICAL_INDEX", "pageCount": count,
            "blocks": blocks, "parts": [], "tableCount": None,
            "visualPages": visual_pages, "coverage": {"physicalPages": list(range(1, count + 1))},
            "issueCodes": ["VISUAL_CONTENT_REQUIRES_REVIEW"] if visual_pages else []}


def extract_source(path: Path, manifest: dict) -> dict:
    """Extract one immutable snapshot and preserve unresolved evidence explicitly."""
    with path.open("rb") as stream:
        raw = stream.read(ResourceBounds().max_file_size_bytes + 1)
    if len(raw) > ResourceBounds().max_file_size_bytes:
        raise ValueError("Source file resource limit exceeded")
    actual_hash = hashlib.sha256(raw).hexdigest()
    if actual_hash != manifest["sha256"].lower():
        raise ValueError("Source snapshot SHA-256 does not match the manifest")
    if path.suffix.lower() != manifest["extension"]:
        raise ValueError("Source extension mismatch")
    if manifest["extension"] == ".docx":
        result = _docx(raw)
    elif manifest["extension"] == ".pdf":
        result = _pdf(raw)
    else:
        raise ValueError("Unsupported source format")
    issue_codes = set(result["issueCodes"])
    if not any(block["rawText"].strip() for block in result["blocks"]):
        issue_codes.add("EMPTY_TEXT_REQUIRES_REVIEW")
    suspicious = []
    for block in result["blocks"]:
        text = block["cleanText"]
        if (any(marker in text for marker in ("Ã©", "Ã£", "Ã§", "Â\u00a0", "â€", "\ufffd"))
                or any(unicodedata.category(char) in ("Cc", "Cs", "Co") and char not in "\n\r\t" for char in text)):
            suspicious.append(block["anchor"])
    if suspicious:
        issue_codes.add("TEXT_QUALITY_REQUIRES_REVIEW")
    result.update(version=1, sourceId=manifest["sourceId"], sourcePath=manifest["path"],
                  sourceSha256=actual_hash, normalizationVersion=NORMALIZATION_VERSION,
                  blockCount=len(result["blocks"]), suspiciousAnchors=suspicious,
                  issueCodes=sorted(issue_codes))
    return result
