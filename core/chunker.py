"""LLM 컨텍스트 예산에 맞게 본문을 잘라내는 보조 — 5스튜디오 풀 본문 호출 시 사용."""
from __future__ import annotations


def fit_to_budget(text: str, budget_chars: int = 60000) -> str:
    """앞쪽 + 뒤쪽 우선, 중간 생략. budget_chars 이하면 그대로 반환."""
    if len(text) <= budget_chars:
        return text
    half = budget_chars // 2 - 200
    return f"{text[:half]}\n\n[... 본문 일부 생략 ...]\n\n{text[-half:]}"
