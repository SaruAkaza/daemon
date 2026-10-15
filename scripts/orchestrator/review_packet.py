"""Build a private, offline review notebook. Notes never certify pipeline stages."""
from __future__ import annotations

import argparse
import base64
from collections import Counter, defaultdict
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import warnings
import xml.etree.ElementTree as ET
import zipfile

from PIL import Image, UnidentifiedImageError

from scripts.agents.application_runtime import ResourceBounds
from scripts.agents.contracts import validate_payload
from scripts.orchestrator.source_extraction import W, extract_source

ROOT = Path(__file__).resolve().parents[2]
ASSETS = Path(__file__).with_name("review_assets")
MAX_MEDIA_BYTES = 64 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
MAX_TOTAL_PIXELS = 100_000_000
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def _read_limited(path: Path) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(ResourceBounds().max_file_size_bytes + 1)
    if len(data) > ResourceBounds().max_file_size_bytes:
        raise ValueError("Review input exceeds the file resource limit")
    return data


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _xml(raw: bytes) -> ET.Element:
    if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        raise ValueError("DTD/entity declarations are not supported")
    return ET.fromstring(raw)


def _usages(package: zipfile.ZipFile, audit: dict) -> tuple[dict, list]:
    """Resolve only internal media relationships; never follow external URLs."""
    usages = defaultdict(set)
    unresolved = []
    for part in audit["parts"]:
        path = part["path"]
        relpath = str(PurePosixPath(path).parent / "_rels" / (PurePosixPath(path).name + ".rels"))
        if relpath not in package.namelist():
            continue
        info = package.getinfo(relpath)
        if info.file_size > 2 * 1024 * 1024:
            raise ValueError("DOCX relationship resource limit exceeded")
        relationships = {item.get("Id"): item for item in _xml(package.read(relpath))}
        root = _xml(package.read(path))
        paths = {root: "/" + root.tag.rsplit("}", 1)[-1] + "[1]"}
        paragraphs = {root: None}
        for element in root.iter():
            anchor = path + "#" + paths[element] if element.tag == W + "p" else paragraphs[element]
            for key in (R + "embed", R + "link", R + "id"):
                rel_id = element.get(key)
                if not rel_id:
                    continue
                rel = relationships.get(rel_id)
                if rel is None or not (rel.get("Type") or "").endswith("/image"):
                    continue
                target = posixpath.normpath(posixpath.join(posixpath.dirname(path), rel.get("Target", "")))
                if (rel.get("TargetMode") == "External" or not target.startswith("word/media/")
                        or target not in package.namelist()):
                    unresolved.append({"part": path, "anchor": anchor, "relationshipId": rel_id})
                elif anchor:
                    usages[target].add(anchor)
            counts = Counter()
            for child in element:
                counts[child.tag] += 1
                paths[child] = paths[element] + "/" + child.tag.rsplit("}", 1)[-1] + f"[{counts[child.tag]}]"
                paragraphs[child] = anchor
    return {key: sorted(values) for key, values in usages.items()}, unresolved


def _media(raw: bytes, audit: dict) -> tuple[list, list]:
    media = []
    total_pixels = 0
    with zipfile.ZipFile(io.BytesIO(raw)) as package:
        if sum(i.file_size for i in package.infolist() if i.filename.endswith(".rels")) > 16 * 1024 * 1024:
            raise ValueError("DOCX relationship resource limit exceeded")
        infos = [i for i in package.infolist() if i.filename.startswith("word/media/") and not i.is_dir()]
        if len(infos) > 2048 or sum(i.file_size for i in infos) > MAX_MEDIA_BYTES:
            raise ValueError("DOCX media resource limit exceeded")
        usages, unresolved = _usages(package, audit)
        for info in sorted(infos, key=lambda item: item.filename):
            data = package.read(info)
            item = {"part": info.filename, "sha256": _sha(data), "sizeBytes": len(data),
                    "anchors": usages.get(info.filename, []), "preview": None, "previewStatus": "UNSUPPORTED"}
            # Only decoded raster pixels are embedded. No SVG, scripts, OLE or original binary downloads.
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", Image.DecompressionBombWarning)
                    with Image.open(io.BytesIO(data)) as image:
                        item.update(width=image.width, height=image.height, frameCount=getattr(image, "n_frames", 1))
                        pixels = image.width * image.height
                        total_pixels += pixels
                        if pixels > MAX_IMAGE_PIXELS or total_pixels > MAX_TOTAL_PIXELS:
                            raise ValueError("DOCX image pixel resource limit exceeded")
                        if image.format not in {"PNG", "JPEG", "GIF", "WEBP", "BMP", "TIFF"}:
                            media.append(item)
                            continue
                        image.seek(0)
                        image.thumbnail((1200, 1200))
                        preview = image.copy() if image.mode in {"P", "L", "LA", "RGB", "RGBA"} else image.convert("RGBA")
                        transparency = preview.info.get("transparency")
                        preview.info.clear()
                        if transparency is not None:
                            preview.info["transparency"] = transparency
                        buffer = io.BytesIO()
                        if image.format == "JPEG":
                            preview.save(buffer, format="JPEG", quality=90)
                            mime = "image/jpeg"
                        else:
                            preview.save(buffer, format="PNG")
                            mime = "image/png"
                        item.update(preview=f"data:{mime};base64," + base64.b64encode(buffer.getvalue()).decode("ascii"),
                                    previewSha256=_sha(buffer.getvalue()), previewStatus="FIRST_FRAME_DERIVATIVE",
                                    previewWidth=preview.width, previewHeight=preview.height)
            except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
                item["previewStatus"] = "UNREADABLE_OR_UNSUPPORTED"
            media.append(item)
    return media, unresolved


def _inline_json(value: dict) -> str:
    # A source paragraph can contain literal HTML closing tags; JSON remains inert.
    return (json.dumps(value, ensure_ascii=True, separators=(",", ":"))
            .replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e"))


def build_review_packet(source: Path, manifest: dict, evidence: Path, *, evidence_sha256: str) -> bytes:
    """Verify byte-bound evidence against the immutable source before rendering."""
    validate_payload("source-manifest", manifest)
    raw_evidence = _read_limited(evidence)
    if _sha(raw_evidence) != evidence_sha256.lower():
        raise ValueError("Review evidence SHA-256 mismatch")
    result = json.loads(raw_evidence)
    validate_payload("execution-result", result)
    audit = extract_source(source, manifest)
    metadata = result.get("metadata", {})
    if (result["stage"] != "extraction" or metadata.get("extraction") != audit
            or metadata.get("sourceId") != manifest["sourceId"]
            or metadata.get("sourceSha256") != manifest["sha256"].lower()):
        raise ValueError("Review evidence differs from source extraction")
    source_bytes = _read_limited(source)
    if _sha(source_bytes) != audit["sourceSha256"]:
        raise ValueError("Source changed while building review packet")
    media, unresolved = _media(source_bytes, audit) if audit["format"] == "docx" else ([], [])
    payload = {"version": 1, "status": "DRAFT_UNVERIFIED", "title": manifest["title"],
               "sourceId": audit["sourceId"], "sourceSha256": audit["sourceSha256"],
               "evidenceSha256": _sha(raw_evidence), "rightsStatus": manifest["rightsStatus"],
               "visibility": "private", "publicationMode": "NOT_PUBLIC", "extraction": audit,
               "media": media, "unresolvedMediaReferences": unresolved}
    css = (ASSETS / "review.css").read_text(encoding="utf-8")
    script = (ASSETS / "review.js").read_text(encoding="utf-8")
    template = (ASSETS / "review.html").read_text(encoding="utf-8")
    def csp_hash(text: str) -> str:
        return base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode("ascii")
    tokens = {"CSS": css, "SCRIPT": script, "DATA": _inline_json(payload),
              "CSS_HASH": csp_hash(css), "SCRIPT_HASH": csp_hash(script)}
    # Substitute template tokens once, never interpret token-like book content.
    html = re.sub(r"@@(CSS|SCRIPT|DATA|CSS_HASH|SCRIPT_HASH)@@", lambda match: tokens[match[1]], template)
    encoded = html.encode("utf-8")
    if len(encoded) > ResourceBounds().max_file_size_bytes:
        raise ValueError("Review packet exceeds the file resource limit")
    return encoded


def write_packet(output: Path, data: bytes) -> Path:
    output = output.resolve()
    if output.is_relative_to(ROOT):
        raise ValueError("Private review output must be outside the repository")
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--evidence-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(_read_limited(args.manifest))
    from scripts.orchestrator.checkpoint_manager import contained_file
    source = contained_file(args.source_root, manifest["path"])
    data = build_review_packet(source, manifest, args.evidence, evidence_sha256=args.evidence_sha256)
    target = write_packet(args.output, data)
    print(json.dumps({"output": str(target), "sha256": _sha(data), "sizeBytes": len(data),
                      "status": "DRAFT_UNVERIFIED", "publicationMode": "NOT_PUBLIC"}))


if __name__ == "__main__":
    main()
