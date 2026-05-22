"""본문 청킹 — LLM 컨텍스트 제한을 넘는 경우 섹션 단위로 자른다."""
from __future__ import annotations

import re

# 한국 교재 본문에서 자주 등장하는 섹션 헤더 패턴
SECTION_PATTERNS = [
    re.compile(r"^\s*제\s*\d+\s*장\b"),
    re.compile(r"^\s*\d+절\b"),
    re.compile(r"^\s*[IVX]+\.\s+\S"),
    re.compile(r"^\s*\d+\.\s+\S"),
    re.compile(r"^\s*\(\d+\)\s+\S"),
]


def looks_like_header(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > 80:
        return False
    return any(p.match(s) for p in SECTION_PATTERNS)


def chunk_by_section(text: str, max_chars: int = 12000) -> list[str]:
    """헤더 같은 라인에서 분할하되, 각 청크가 max_chars 를 넘지 않게 추가 분할."""
    if len(text) <= max_chars:
        return [text]

    lines = text.splitlines()
    chunks: list[list[str]] = [[]]

    for line in lines:
        current_size = sum(len(s) for s in chunks[-1])
        if looks_like_header(line) and current_size > max_chars * 0.6:
            chunks.append([])
        elif current_size + len(line) > max_chars:
            chunks.append([])
        chunks[-1].append(line)

    return ["\n".join(c).strip() for c in chunks if c]


def fit_to_budget(text: str, budget_chars: int = 60000) -> str:
    """LLM 컨텍스트 예산에 맞게 본문을 자른다 (앞쪽 + 뒤쪽 우선, 중간 생략)."""
    if len(text) <= budget_chars:
        return text
    half = budget_chars // 2 - 200
    return f"{text[:half]}\n\n[... 본문 일부 생략 ...]\n\n{text[-half:]}"
