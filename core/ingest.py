"""PDF / 텍스트 / HWPX 인제스트. pymupdf + zipfile + xml.etree 기반."""
from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

import fitz  # pymupdf


@dataclass
class IngestedPage:
    page_no: int
    text: str


@dataclass
class IngestedDoc:
    source_id: str
    filename: str
    pages: list[IngestedPage] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n\n".join(f"[p.{p.page_no}]\n{p.text}" for p in self.pages if p.text.strip())

    @property
    def page_count(self) -> int:
        return len(self.pages)


def ingest_pdf(path: str | Path, source_id: str | None = None) -> IngestedDoc:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)

    sid = source_id or p.stem
    doc = IngestedDoc(source_id=sid, filename=p.name)

    with fitz.open(p) as pdf:
        for i, page in enumerate(pdf, start=1):
            text = page.get_text("text") or ""
            doc.pages.append(IngestedPage(page_no=i, text=text.strip()))

    return doc


def ingest_text(path: str | Path, source_id: str | None = None) -> IngestedDoc:
    p = Path(path)
    sid = source_id or p.stem
    body = p.read_text(encoding="utf-8", errors="ignore")
    return IngestedDoc(
        source_id=sid,
        filename=p.name,
        pages=[IngestedPage(page_no=1, text=body)],
    )


def ingest_hwpx(path: str | Path, source_id: str | None = None) -> IngestedDoc:
    """HWPX (한컴오피스) 텍스트 추출. ZIP 안 Contents/section*.xml 의 <t> 노드를 모은다."""
    p = Path(path)
    sid = source_id or p.stem

    text_parts: list[str] = []
    with zipfile.ZipFile(p, "r") as z:
        # Contents/section0.xml, section1.xml ... 본문이 있는 파일
        section_files = sorted(
            n for n in z.namelist()
            if "section" in n.lower() and n.endswith(".xml")
        )
        if not section_files:
            # 폴백: 모든 XML
            section_files = [n for n in z.namelist() if n.endswith(".xml")]

        for name in section_files:
            try:
                with z.open(name) as f:
                    tree = ET.parse(f)
                root = tree.getroot()
                # 네임스페이스 무시하고 local-name 이 't' 또는 'char' 인 노드의 텍스트 수집
                for elem in root.iter():
                    local = elem.tag.split("}", 1)[-1] if "}" in elem.tag else elem.tag
                    if local in ("t", "char") and elem.text:
                        text_parts.append(elem.text)
                    # 문단 끝마다 줄바꿈
                    if local in ("p", "para") and text_parts and not text_parts[-1].endswith("\n"):
                        text_parts.append("\n")
            except ET.ParseError:
                continue

    body = "".join(text_parts).strip()
    return IngestedDoc(
        source_id=sid,
        filename=p.name,
        pages=[IngestedPage(page_no=1, text=body)],
    )


def ingest_any(path: str | Path, source_id: str | None = None) -> IngestedDoc:
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        return ingest_pdf(p, source_id)
    if suffix in (".txt", ".md"):
        return ingest_text(p, source_id)
    if suffix == ".hwpx":
        return ingest_hwpx(p, source_id)
    raise ValueError(f"지원하지 않는 형식: {suffix}")


def merge_docs(docs: Iterable[IngestedDoc]) -> str:
    parts: list[str] = []
    for d in docs:
        parts.append(f"\n\n===== 소스: {d.filename} =====\n\n{d.full_text}")
    return "".join(parts).strip()
