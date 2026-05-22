"""활성 소스 상태 관리 — 원본 local-notebooklm 의 "소스 N개" 카운트 버그 수정.

체크된 소스만 카운트하고, 0개일 때는 모든 스튜디오 버튼을 비활성화한다.
Streamlit `st.session_state["active_sources"]` 가 단일 진실 소스(SSOT).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SourceEntry:
    source_id: str
    filename: str
    path: Path
    active: bool = True


@dataclass
class SourceRegistry:
    sources: dict[str, SourceEntry] = field(default_factory=dict)

    # ---- mutation ----
    def add(self, source_id: str, filename: str, path: str | Path, active: bool = True) -> SourceEntry:
        entry = SourceEntry(source_id=source_id, filename=filename, path=Path(path), active=active)
        self.sources[source_id] = entry
        return entry

    def remove(self, source_id: str) -> None:
        self.sources.pop(source_id, None)

    def set_active(self, source_id: str, active: bool) -> None:
        if source_id in self.sources:
            self.sources[source_id].active = active

    def toggle(self, source_id: str) -> bool:
        if source_id in self.sources:
            self.sources[source_id].active = not self.sources[source_id].active
            return self.sources[source_id].active
        return False

    # ---- queries ----
    @property
    def total_count(self) -> int:
        return len(self.sources)

    @property
    def active_count(self) -> int:
        return sum(1 for s in self.sources.values() if s.active)

    @property
    def has_any_active(self) -> bool:
        return self.active_count > 0

    def active_sources(self) -> list[SourceEntry]:
        return [s for s in self.sources.values() if s.active]

    def all_sources(self) -> list[SourceEntry]:
        return list(self.sources.values())

    # ---- UI helpers ----
    def header_label(self) -> str:
        """채팅 헤더 표시 라벨 — 버그 수정 후 동작."""
        if self.total_count == 0:
            return "· 소스 없음 (먼저 업로드하세요)"
        if self.active_count == 0:
            return f"· 소스 없음 (체크하세요) · 등록 {self.total_count}개"
        return f"· 소스 {self.active_count}/{self.total_count}개"

    def studio_disabled_reason(self) -> str | None:
        """스튜디오 버튼 disabled 사유. None 이면 활성."""
        if self.total_count == 0:
            return "먼저 PDF를 업로드하세요"
        if self.active_count == 0:
            return "최소 1개의 소스에 체크하세요"
        return None
