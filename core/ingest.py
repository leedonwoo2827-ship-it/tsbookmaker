"""PDF / 텍스트 인제스트. pymupdf 기반, 페이지별 텍스트 + 메타 반환."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

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


def ingest_any(path: str | Path, source_id: str | None = None) -> IngestedDoc:
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        return ingest_pdf(p, source_id)
    if suffix in (".txt", ".md"):
        return ingest_text(p, source_id)
    raise ValueError(f"지원하지 않는 형식: {suffix}")


def merge_docs(docs: Iterable[IngestedDoc]) -> str:
    parts: list[str] = []
    for d in docs:
        parts.append(f"\n\n===== 소스: {d.filename} =====\n\n{d.full_text}")
    return "".join(parts).strip()
