"""Source ingestion helpers for TXT and EPUB novels."""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
import json
import re
import zipfile
import xml.etree.ElementTree as ET


CHAPTER_HEADING_RE = re.compile(
    r"^\s*((?:chapter|ch\.)\s+\d+[\w\s:.\-]*|第\s*[\d一二两三四五六七八九十百千万零〇]+\s*[章节回卷][^\n]*)\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Chapter:
    index: int
    title: str
    text: str


@dataclass(frozen=True)
class ParsedSource:
    title: str
    full_text: str
    chapters: list[Chapter]


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self._in_body = False
        self._in_title = False
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_name = tag.lower()
        if tag_name == "body":
            self._in_body = True
        elif tag_name == "title":
            self._in_title = True
        elif tag_name in {"script", "style"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        tag_name = tag.lower()
        if tag_name == "body":
            self._in_body = False
        elif tag_name == "title":
            self._in_title = False
        elif tag_name in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        stripped = data.strip()
        if self._in_title and stripped:
            self.title_parts.append(stripped)
        if self._in_body and not self._skip_depth and stripped:
            self.parts.append(stripped)

    def get_text(self) -> str:
        return "\n".join(self.parts)

    def get_title(self) -> str:
        return " ".join(self.title_parts).strip()


def normalize_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip() + "\n"


def parse_txt(text: str, fallback_title: str = "Untitled Novel") -> ParsedSource:
    full_text = normalize_text(text)
    lines = full_text.splitlines()
    non_empty = [line.strip() for line in lines if line.strip()]
    title = non_empty[0] if non_empty and not CHAPTER_HEADING_RE.match(non_empty[0]) else fallback_title

    heading_positions: list[int] = []
    for index, line in enumerate(lines):
        if CHAPTER_HEADING_RE.match(line):
            heading_positions.append(index)

    if not heading_positions:
        body = "\n".join(lines[1:]).strip() if title != fallback_title and len(lines) > 1 else full_text.strip()
        chapter_text = body if body else full_text.strip()
        return ParsedSource(title=title, full_text=full_text, chapters=[Chapter(1, "Chapter 1", chapter_text)])

    chapters: list[Chapter] = []
    for chapter_number, start in enumerate(heading_positions, start=1):
        end = heading_positions[chapter_number] if chapter_number < len(heading_positions) else len(lines)
        chapter_title = lines[start].strip()
        chapter_body = "\n".join(lines[start + 1 : end]).strip()
        chapters.append(Chapter(chapter_number, chapter_title, chapter_body))

    return ParsedSource(title=title, full_text=full_text, chapters=chapters)


def parse_epub(path: str | Path) -> ParsedSource:
    epub_path = Path(path)
    with zipfile.ZipFile(epub_path) as archive:
        opf_path = _find_opf_path(archive)
        opf_root = ET.fromstring(archive.read(opf_path))
        namespace = _xml_namespace(opf_root.tag)
        book_title = _epub_metadata_title(opf_root) or epub_path.stem
        manifest = _epub_manifest(opf_root, namespace)
        spine = _epub_spine(opf_root, namespace)
        base_dir = str(Path(opf_path).parent)
        chapters: list[Chapter] = []
        for item_id in spine:
            href = manifest.get(item_id)
            if not href:
                continue
            item_path = str(Path(base_dir) / href) if base_dir != "." else href
            if item_path not in archive.namelist():
                continue
            extractor = _HTMLTextExtractor()
            extractor.feed(archive.read(item_path).decode("utf-8", errors="ignore"))
            body_lines = _clean_epub_lines(extractor.get_text().splitlines())
            if _is_boilerplate_page(body_lines, book_title):
                continue
            chapter_title, chapter_text = _chapter_from_epub_lines(extractor.get_title(), body_lines)
            if not chapter_text:
                continue
            chapters.append(Chapter(index=len(chapters) + 1, title=chapter_title, text=chapter_text))

    full_text = normalize_text("\n\n".join([book_title, *[f"{chapter.title}\n{chapter.text}" for chapter in chapters]]))
    return ParsedSource(title=book_title, full_text=full_text, chapters=chapters)


def parse_source_file(path: str | Path) -> ParsedSource:
    source_path = Path(path)
    suffix = source_path.suffix.lower()
    if suffix == ".txt":
        return parse_txt(source_path.read_text(encoding="utf-8"), fallback_title=source_path.stem)
    if suffix == ".epub":
        return parse_epub(source_path)
    raise ValueError(f"Unsupported source format: {source_path.suffix}")


def write_parsed_source(parsed: ParsedSource, output_dir: str | Path) -> None:
    target = Path(output_dir)
    chapters_dir = target / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)

    (target / "novel.txt").write_text(parsed.full_text, encoding="utf-8")
    manifest = {
        "title": parsed.title,
        "chapter_count": len(parsed.chapters),
        "chapters": [
            {
                "index": chapter.index,
                "title": chapter.title,
                "path": f"chapters/ch{chapter.index:03d}.txt",
                "characters": len(chapter.text),
            }
            for chapter in parsed.chapters
        ],
    }
    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for chapter in parsed.chapters:
        chapter_content = f"{chapter.title}\n\n{chapter.text.strip()}\n"
        (chapters_dir / f"ch{chapter.index:03d}.txt").write_text(chapter_content, encoding="utf-8")


def _find_opf_path(archive: zipfile.ZipFile) -> str:
    container = ET.fromstring(archive.read("META-INF/container.xml"))
    rootfile = container.find(".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile")
    if rootfile is None:
        raise ValueError("EPUB container does not declare a rootfile")
    full_path = rootfile.attrib.get("full-path")
    if not full_path:
        raise ValueError("EPUB rootfile has no full-path")
    return full_path


def _xml_namespace(tag: str) -> dict[str, str]:
    if tag.startswith("{"):
        return {"opf": tag[1:].split("}", 1)[0]}
    return {"opf": ""}


def _epub_manifest(root: ET.Element, namespace: dict[str, str]) -> dict[str, str]:
    manifest: dict[str, str] = {}
    for item in root.findall(".//opf:manifest/opf:item", namespace):
        media_type = item.attrib.get("media-type", "")
        if "html" not in media_type and "xhtml" not in media_type:
            continue
        item_id = item.attrib.get("id")
        href = item.attrib.get("href")
        if item_id and href:
            manifest[item_id] = href
    return manifest


def _epub_spine(root: ET.Element, namespace: dict[str, str]) -> list[str]:
    return [
        item.attrib["idref"]
        for item in root.findall(".//opf:spine/opf:itemref", namespace)
        if "idref" in item.attrib
    ]


def _epub_metadata_title(root: ET.Element) -> str:
    for element in root.iter():
        if element.tag.endswith("title") and element.text and element.text.strip():
            return element.text.strip().strip("《》")
    return ""


def _clean_epub_lines(lines: list[str]) -> list[str]:
    cleaned: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped in {"Txt,Epub,Mobi"}:
            continue
        if re.search(r"https?://|www\.", stripped, re.IGNORECASE):
            continue
        cleaned.append(stripped)
    return cleaned


def _is_boilerplate_page(lines: list[str], book_title: str) -> bool:
    if not lines:
        return True
    meaningful = [line.strip("《》") for line in lines if not line.startswith("作者")]
    return len(meaningful) <= 1 and meaningful[0] == book_title if meaningful else True


def _chapter_from_epub_lines(html_title: str, lines: list[str]) -> tuple[str, str]:
    title = html_title.strip().strip("《》") or "Chapter"
    body_lines = list(lines)
    if body_lines and body_lines[0].strip("《》") == title.strip("《》"):
        body_lines.pop(0)
    if body_lines and _looks_like_heading(body_lines[0]):
        nested_title = body_lines.pop(0)
        if title and not _same_heading(title, nested_title):
            title = f"{title} · {nested_title}" if title.startswith("第") and "卷" in title else nested_title
        else:
            title = nested_title
    return title, "\n".join(body_lines).strip()


def _looks_like_heading(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("序章") or bool(CHAPTER_HEADING_RE.match(stripped))


def _same_heading(left: str, right: str) -> bool:
    return left.strip().strip("《》") == right.strip().strip("《》")
