"""스튜디오 레지스트리 — 5개 스튜디오만 등록.

버튼 배치 순서: ① 앞부속 → ② 단원학습정리 → ③ 학습평가 → ④ 퀴즈 → ⑤ 슬라이드 교안
"""
from __future__ import annotations

from studio._base import StudioBase
from studio.chapter_intro import ChapterIntroStudio
from studio.chapter_summary import ChapterSummaryStudio
from studio.chapter_assessment import ChapterAssessmentStudio
from studio.quiz import QuizStudio
from studio.slide_deck import SlideDeckStudio


REGISTRY: list[StudioBase] = [
    ChapterIntroStudio(),       # ①
    ChapterSummaryStudio(),     # ②
    ChapterAssessmentStudio(),  # ③
    QuizStudio(),               # ④
    SlideDeckStudio(),          # ⑤
]


def list_studios() -> list[StudioBase]:
    return sorted(REGISTRY, key=lambda s: s.order)


def get_studio(key: str) -> StudioBase:
    for s in REGISTRY:
        if s.key == key:
            return s
    raise KeyError(f"미등록 스튜디오: {key}")
