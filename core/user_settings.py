"""사용자 설정 — Streamlit GUI 에서 입력받아 JSON 으로 보존.

교수자분들이 cmd 나 .env 를 만지지 않고 화면에서 URL/Key 만 입력하고
프리셋(저렴/균형/프리미엄) 버튼만 누르면 바로 LLM 호출이 작동하도록 한다.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

SETTINGS_FILE = Path(__file__).resolve().parent.parent / "data" / "user_settings.json"


# 프리셋 — 모델 카탈로그(Ubion LiteLLM) 기준. 키: 화면 표시명, 값: 실제 모델 식별자.
PRESETS: dict[str, dict[str, str]] = {
    "frugal": {
        "label": "💰 저렴",
        "model": "deepseek-v4-flash",
        "desc": "비용 최저 · 챕터 1개 ≈ 1천원 · 한국어 OK",
    },
    "balanced": {
        "label": "⚖ 균형",
        "model": "claude-sonnet-4-6",
        "desc": "품질·비용 균형 · 챕터 1개 ≈ 3~5천원 · 한국어 강함",
    },
    "premium": {
        "label": "💎 프리미엄",
        "model": "claude-opus-4-7",
        "desc": "최고 품질 · 챕터 1개 ≈ 7천원 이상 · 최종본·고난도 작업",
    },
}
DEFAULT_PRESET = "frugal"


def preset_to_model(preset: str) -> str:
    return PRESETS.get(preset, PRESETS[DEFAULT_PRESET])["model"]


def model_to_preset(model: str) -> str | None:
    for key, p in PRESETS.items():
        if p["model"] == model:
            return key
    return None


@dataclass
class UserSettings:
    api_base: str = ""                      # 예: http://192.168.50.119:4000 (회사 LiteLLM)
    api_key: str = ""                       # 회사 발급 virtual key (sk-...)
    preset: str = DEFAULT_PRESET            # frugal | balanced | premium
    model: str = "deepseek-v4-flash"        # 프리셋이 결정 (직접 수정 비권장)
    temperature: float = 0.3
    max_tokens: int = 8000

    @property
    def is_configured(self) -> bool:
        return bool(self.api_base.strip()) and bool(self.api_key.strip())

    def safe_api_key_preview(self) -> str:
        k = self.api_key or ""
        if not k:
            return "(미입력)"
        if len(k) <= 8:
            return "***"
        return f"{k[:4]}…{k[-4:]}"

    def preset_label(self) -> str:
        return PRESETS.get(self.preset, PRESETS[DEFAULT_PRESET])["label"]


def load() -> UserSettings:
    """저장된 설정을 읽어 반환. 파일이 없으면 환경변수 또는 빈 설정 반환."""
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            # 알려진 필드만 통과시킨다 (구버전 호환)
            known = {k: v for k, v in data.items() if k in UserSettings.__annotations__}
            s = UserSettings(**known)
            # preset 과 model 정합성 보정 — preset 이 있고 model 이 비어있거나 안 맞으면 preset 우선
            if s.preset in PRESETS:
                expected = preset_to_model(s.preset)
                if not s.model or s.model not in {p["model"] for p in PRESETS.values()}:
                    s.model = expected
            return s
        except (json.JSONDecodeError, TypeError):
            pass

    # 파일 없거나 파싱 실패 → 환경변수 fallback (Ubion 키트의 UBION_LITELLM_* 도 인식)
    return UserSettings(
        api_base=(
            os.getenv("UBION_LITELLM_URL", "")
            or os.getenv("DEEPSEEK_API_BASE", "")
            or os.getenv("OPENAI_API_BASE", "")
        ),
        api_key=(
            os.getenv("UBION_LITELLM_KEY", "")
            or os.getenv("DEEPSEEK_API_KEY", "")
            or os.getenv("OPENAI_API_KEY", "")
        ),
        preset=DEFAULT_PRESET,
        model=preset_to_model(DEFAULT_PRESET),
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
