"""사용자 설정 — Streamlit GUI 에서 입력받아 JSON 으로 보존.

교수자분들이 cmd 나 .env 를 만지지 않고 화면에서 URL/Key/Model 만 입력하면
바로 LLM 호출이 작동하도록 한다.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

SETTINGS_FILE = Path(__file__).resolve().parent.parent / "data" / "user_settings.json"


@dataclass
class UserSettings:
    api_base: str = ""              # 예: https://llm.mycompany.com/v1
    api_key: str = ""               # 회사 발급 API 키
    model: str = "deepseek-v4"      # 기본 모델 이름 (회사 게이트웨이가 다른 이름이면 변경)
    temperature: float = 0.3
    max_tokens: int = 8000

    # 보조 모델 (선택 입력) — UI 드롭다운에서 전환할 때 사용
    alt_models: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.alt_models is None:
            self.alt_models = []

    @property
    def is_configured(self) -> bool:
        return bool(self.api_base.strip()) and bool(self.api_key.strip())

    def safe_api_key_preview(self) -> str:
        """API 키 일부만 마스킹해서 보여주기 (UI 표시용)."""
        k = self.api_key or ""
        if not k:
            return "(미입력)"
        if len(k) <= 8:
            return "***"
        return f"{k[:4]}…{k[-4:]}"


def load() -> UserSettings:
    """저장된 설정을 읽어 반환. 파일이 없으면 .env 기본값 또는 빈 설정 반환."""
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            return UserSettings(**{k: v for k, v in data.items() if k in UserSettings.__annotations__})
        except (json.JSONDecodeError, TypeError):
            pass

    # 파일 없거나 파싱 실패 → .env 디폴트로 fallback
    return UserSettings(
        api_base=os.getenv("DEEPSEEK_API_BASE", "") or os.getenv("OPENAI_API_BASE", ""),
        api_key=os.getenv("DEEPSEEK_API_KEY", "") or os.getenv("OPENAI_API_KEY", ""),
        model=os.getenv("TSB_LLM_MODEL_DEEPSEEK", "deepseek-v4"),
        temperature=float(os.getenv("TSB_LLM_TEMPERATURE", "0.3")),
        max_tokens=int(os.getenv("TSB_LLM_MAX_TOKENS", "8000")),
    )


def save(settings: UserSettings) -> Path:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(
        json.dumps(asdict(settings), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return SETTINGS_FILE
