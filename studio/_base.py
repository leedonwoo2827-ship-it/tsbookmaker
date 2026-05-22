"""스튜디오 베이스 — 모든 산출물 생성기의 공통 인터페이스."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class StudioContext:
    """스튜디오 호출 시 주입되는 컨텍스트 — 활성 소스 본문 + 출력 경로 + 모델."""

    body_text: str
    output_dir: Path
    notebook_id: str
    chapter_hint: str = ""        # 예: "ch01" — 산출물 폴더 prefix
    model: str | None = None      # UI 드롭다운 선택값 (None 이면 .env 디폴트)
    metadata: dict = field(default_factory=dict)


@dataclass
class StudioResult:
    studio: str
    primary_path: Path                          # 메인 산출물 (MD)
    artifacts: list[Path] = field(default_factory=list)  # 보조 산출물 (xlsx 등)
    summary: str = ""

    def all_paths(self) -> list[Path]:
        return [self.primary_path, *self.artifacts]


class StudioBase(ABC):
    """모든 스튜디오는 이 클래스를 상속한다."""

    key: str = ""               # 등록 키 (registry.py 에서 사용)
    label: str = ""             # UI 버튼 라벨
    icon: str = "📄"
    order: int = 99             # UI 정렬 순서

    @abstractmethod
    def run(self, ctx: StudioContext) -> StudioResult: ...

    # 편의 메서드
    def write_md(self, ctx: StudioContext, filename: str, body: str) -> Path:
        target = ctx.output_dir / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        return target
