"""공통 MD 작성기 — 한컴오피스/MS Word 가져오기를 전제로 깔끔한 마크다운 생성."""
from __future__ import annotations

from typing import Iterable


def h1(text: str) -> str:
    return f"# {text.strip()}\n"


def h2(text: str) -> str:
    return f"## {text.strip()}\n"


def h3(text: str) -> str:
    return f"### {text.strip()}\n"


def bullets(items: Iterable[str], indent: int = 0) -> str:
    pad = "  " * indent
    return "\n".join(f"{pad}- {str(i).strip()}" for i in items if str(i).strip()) + "\n"


def numbered(items: Iterable[str]) -> str:
    return "\n".join(f"{i + 1}. {str(s).strip()}" for i, s in enumerate(items) if str(s).strip()) + "\n"


def gfm_table(headers: list[str], rows: list[list[str]]) -> str:
    head = "| " + " | ".join(headers) + " |"
    sep = "|" + "|".join(["---"] * len(headers)) + "|"
    body = "\n".join("| " + " | ".join(str(c).replace("|", "/").strip() for c in r) + " |" for r in rows)
    return f"{head}\n{sep}\n{body}\n"


def paragraph(text: str) -> str:
    return text.strip() + "\n"


def join(*blocks: str) -> str:
    return "\n".join(b.rstrip() for b in blocks if b and b.strip()) + "\n"
