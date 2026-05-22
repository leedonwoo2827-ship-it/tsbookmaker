"""LLM 호출 — 사용자가 화면에서 입력한 URL/Key/Model 로 OpenAI-compatible API 직접 호출.

회사 LLM 게이트웨이는 대부분 OpenAI 호환 `/v1/chat/completions` 엔드포인트를 제공한다.
DeepSeek, OpenAI, 그리고 대부분의 회사 LLM 프록시가 동일 포맷을 따른다.
"""
from __future__ import annotations

import json

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from core import user_settings


class LLMConfigError(RuntimeError):
    """API 키/URL 미설정 등 설정 오류."""


def _normalize_base(api_base: str) -> str:
    base = (api_base or "").rstrip("/")
    if not base:
        return ""
    # 흔한 실수: 사용자가 /v1 까지 안 붙이고 들어옴 → 자동 보정
    if not base.endswith("/v1"):
        # 단, 이미 /chat/completions 까지 적었으면 그대로 둠
        if "/chat/completions" not in base:
            base = base + "/v1"
    return base


def _endpoint(api_base: str) -> str:
    base = _normalize_base(api_base)
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=20), reraise=True)
def _post(url: str, headers: dict, payload: dict, timeout: float) -> dict:
    with httpx.Client(timeout=timeout) as client:
        r = client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        return r.json()


def call(
    system: str,
    user: str,
    *,
    model: str | None = None,
    json_mode: bool = False,
    settings: user_settings.UserSettings | None = None,
) -> str:
    s = settings or user_settings.load()
    if not s.is_configured:
        raise LLMConfigError(
            "API 설정이 비어 있습니다. 우측 상단 ⚙ 설정에서 API URL과 키를 입력해 주세요."
        )

    headers = {
        "Authorization": f"Bearer {s.api_key}",
        "Content-Type": "application/json",
    }
    payload: dict = {
        "model": model or s.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": s.temperature,
        "max_tokens": s.max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    data = _post(_endpoint(s.api_base), headers, payload, timeout=180.0)
    return data["choices"][0]["message"]["content"]


def call_json(
    system: str,
    user: str,
    *,
    model: str | None = None,
    settings: user_settings.UserSettings | None = None,
) -> dict:
    raw = call(system, user, model=model, json_mode=True, settings=settings)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # JSON 파싱 실패 → 1회 자동 복구
        repaired = call(
            "You are a JSON repair tool. Return ONLY a valid JSON object.",
            f"Repair this into valid JSON and return only the JSON object:\n{raw}",
            model=model,
            json_mode=True,
            settings=settings,
        )
        return json.loads(repaired)


def list_available_models(settings: user_settings.UserSettings | None = None) -> list[str]:
    """UI 드롭다운용 — 기본 모델 + 사용자가 추가한 보조 모델."""
    s = settings or user_settings.load()
    models = [s.model] if s.model else []
    for m in s.alt_models or []:
        if m and m not in models:
            models.append(m)
    return models or ["deepseek-v4"]


def test_connection(settings: user_settings.UserSettings) -> tuple[bool, str]:
    """설정 패널의 '연결 테스트' 버튼 — 짧은 핑 호출."""
    if not settings.is_configured:
        return False, "API URL 또는 키가 비어 있습니다."
    try:
        out = call(
            "You are a connection test.",
            "Reply with exactly: pong",
            settings=settings,
        )
        return True, f"OK — 응답: {out.strip()[:80]}"
    except httpx.HTTPStatusError as e:
        return False, f"HTTP {e.response.status_code} — {e.response.text[:200]}"
    except Exception as e:  # noqa: BLE001
        return False, f"오류: {type(e).__name__} — {e}"
