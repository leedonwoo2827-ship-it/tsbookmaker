"""LLM 호출 — 사용자가 화면에서 입력한 URL/Key/Model 로 OpenAI-compatible API 직접 호출.

회사 LLM 게이트웨이는 대부분 OpenAI 호환 `/v1/chat/completions` 엔드포인트를 제공한다.
DeepSeek, OpenAI, 그리고 대부분의 회사 LLM 프록시가 동일 포맷을 따른다.

JSON 출력 강제는 `response_format` 파라미터 대신 프롬프트로 처리한다.
일부 회사 게이트웨이가 response_format 을 거절(400)하기 때문이며, JSON 복구 fallback 도
함께 두어 모델이 코드 펜스나 부가 설명을 섞어 보내도 파싱이 가능하다.
"""
from __future__ import annotations

import json
import re

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from core import user_settings


class LLMConfigError(RuntimeError):
    """API 키/URL 미설정 등 설정 오류."""


# Ubion LiteLLM 마이그레이션 키트 함정 #1:
# 신 OpenAI 모델군은 `max_tokens` 를 안 받고 `max_completion_tokens` 만 받는다.
# 다른 모델(Claude / DeepSeek / Gemini 등)은 `max_tokens` 그대로 사용 가능.
_NEW_OPENAI_MODELS = {
    "gpt-5.5",
    "gpt-5.5-pro",
    "chat-latest",
    "gpt-5.4-mini",
    "gpt-5.4-nano",
}


def _apply_max_tokens(payload: dict, model: str, max_tokens: int) -> None:
    """모델 종류에 따라 max_tokens / max_completion_tokens 자동 선택."""
    if model in _NEW_OPENAI_MODELS:
        payload["max_completion_tokens"] = max_tokens
    else:
        payload["max_tokens"] = max_tokens


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


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=2, max=20),
    reraise=True,
    # 4xx 는 게이트웨이가 명시적으로 거절한 것이므로 재시도해도 같은 결과 → 네트워크/타임아웃만 재시도
    retry=retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException)),
)
def _post(url: str, headers: dict, payload: dict, timeout: float) -> dict:
    with httpx.Client(timeout=timeout) as client:
        r = client.post(url, headers=headers, json=payload)
        if r.is_error:
            body = r.text[:2000] if r.text else "(빈 응답)"
            model = payload.get("model")
            max_tok = payload.get("max_tokens")
            json_mode = "response_format" in payload
            raise httpx.HTTPStatusError(
                (
                    f"HTTP {r.status_code} from {url}\n"
                    f"\n--- Gateway 응답 본문 ---\n{body}\n"
                    f"\n--- 요청 요약 ---\n"
                    f"model={model!r}  max_tokens={max_tok}  json_mode={json_mode}\n"
                    f"\n흔한 원인:\n"
                    f"  • 모델 이름이 게이트웨이에 등록되어 있지 않음 → ⚙ 설정에서 모델 이름 확인 후 변경\n"
                    f"  • max_tokens 가 모델 한도(4096 등)를 초과 → ⚙ 설정에서 줄이기\n"
                    f"  • API 키가 만료/오타 → 담당자에게 재발급 요청\n"
                ),
                request=r.request,
                response=r,
            )
        return r.json()


def call(
    system: str,
    user: str,
    *,
    model: str | None = None,
    settings: user_settings.UserSettings | None = None,
) -> str:
    s = settings or user_settings.load()
    if not s.is_configured:
        raise LLMConfigError(
            "API 설정이 비어 있습니다. 좌측 ⚙ 설정에서 API URL과 키를 입력해 주세요."
        )

    headers = {
        "Authorization": f"Bearer {s.api_key}",
        "Content-Type": "application/json",
    }
    chosen_model = model or s.model
    payload: dict = {
        "model": chosen_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": s.temperature,
    }
    _apply_max_tokens(payload, chosen_model, s.max_tokens)

    data = _post(_endpoint(s.api_base), headers, payload, timeout=180.0)
    return data["choices"][0]["message"]["content"]


_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(?P<body>.*?)\n?```", re.DOTALL)


def _extract_json(text: str) -> str:
    """LLM 응답에서 JSON 본문만 추출. 코드 펜스나 앞뒤 잡설을 제거한다."""
    s = (text or "").strip()
    m = _CODE_FENCE_RE.search(s)
    if m:
        s = m.group("body").strip()
    # 가장 바깥 { ... } 만 잘라낸다
    start = s.find("{")
    end = s.rfind("}")
    if start >= 0 and end > start:
        return s[start : end + 1]
    return s


def call_json(
    system: str,
    user: str,
    *,
    model: str | None = None,
    settings: user_settings.UserSettings | None = None,
) -> dict:
    raw = call(system, user, model=model, settings=settings)
    text = _extract_json(raw)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # JSON 파싱 실패 → 1회 자동 복구
        repaired = call(
            "You are a JSON repair tool. Return ONLY a valid JSON object, with no code fences and no extra prose.",
            f"Repair this into valid JSON and return only the JSON object:\n{raw}",
            model=model,
            settings=settings,
        )
        return json.loads(_extract_json(repaired))


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
