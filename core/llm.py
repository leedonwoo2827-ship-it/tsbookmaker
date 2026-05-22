"""LLM 라우터 — LiteLLM 프록시 경유, DeepSeek V4 디폴트.

UI 드롭다운에서 모델을 변경하면 `call(model=...)` 인자로 즉시 라우팅 키가 바뀐다.
LiteLLM 프록시(`litellm_config.yaml`)에 deepseek-v4 / claude-opus-4-7 / gpt-4o
세 키가 등록되어 있다.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential


DEFAULT_PROVIDER_MODEL = {
    "deepseek": "deepseek-v4",
    "claude": "claude-opus-4-7",
    "openai": "gpt-4o",
}


@dataclass
class LLMConfig:
    proxy_url: str
    master_key: str
    model: str
    temperature: float = 0.3
    max_tokens: int = 8000
    timeout: float = 180.0

    @classmethod
    def from_env(cls, model: str | None = None) -> "LLMConfig":
        port = os.getenv("TSB_LITELLM_PORT", "4610")
        provider = os.getenv("TSB_LLM_PROVIDER", "deepseek").lower()
        env_key = f"TSB_LLM_MODEL_{provider.upper()}"
        default_model = os.getenv(env_key) or DEFAULT_PROVIDER_MODEL.get(provider, "deepseek-v4")
        return cls(
            proxy_url=os.getenv("TSB_LITELLM_URL", f"http://localhost:{port}"),
            master_key=os.getenv("LITELLM_MASTER_KEY", "sk-litellm-master-tsbm"),
            model=model or default_model,
            temperature=float(os.getenv("TSB_LLM_TEMPERATURE", "0.3")),
            max_tokens=int(os.getenv("TSB_LLM_MAX_TOKENS", "8000")),
        )


def resolve_model_key(provider_or_model: str) -> str:
    """UI 드롭다운에서 받은 'deepseek' / 'claude' / 'openai' 별칭을 실제 모델 키로 변환.
    이미 모델 키('deepseek-v4' 등)면 그대로 반환."""
    key = (provider_or_model or "").strip().lower()
    if key in DEFAULT_PROVIDER_MODEL:
        env_key = f"TSB_LLM_MODEL_{key.upper()}"
        return os.getenv(env_key) or DEFAULT_PROVIDER_MODEL[key]
    return provider_or_model


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=20), reraise=True)
def _post_chat(cfg: LLMConfig, messages: list[dict[str, Any]], response_format: dict | None = None) -> dict:
    headers = {
        "Authorization": f"Bearer {cfg.master_key}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": cfg.model,
        "messages": messages,
        "temperature": cfg.temperature,
        "max_tokens": cfg.max_tokens,
    }
    if response_format:
        payload["response_format"] = response_format

    with httpx.Client(timeout=cfg.timeout) as client:
        r = client.post(f"{cfg.proxy_url}/v1/chat/completions", headers=headers, json=payload)
        r.raise_for_status()
        return r.json()


def call(
    system: str,
    user: str,
    *,
    model: str | None = None,
    json_mode: bool = False,
) -> str:
    """단일 user 메시지 호출. json_mode=True 면 응답을 JSON 으로 강제."""
    cfg = LLMConfig.from_env(model=resolve_model_key(model) if model else None)
    response_format = {"type": "json_object"} if json_mode else None
    data = _post_chat(
        cfg,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format=response_format,
    )
    return data["choices"][0]["message"]["content"]


def call_json(system: str, user: str, *, model: str | None = None) -> dict:
    """JSON 응답을 dict 로 파싱해서 반환. 파싱 실패 시 한 번 더 재시도."""
    raw = call(system, user, model=model, json_mode=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        repaired = call(
            "You are a JSON repair tool. Return ONLY valid JSON.",
            f"Repair this into valid JSON and return only the JSON object:\n{raw}",
            model=model,
            json_mode=True,
        )
        return json.loads(repaired)


def list_available_models() -> list[str]:
    """UI 드롭다운용 — env 에 등록된 모델 키 리스트."""
    keys: list[str] = []
    for provider, fallback in DEFAULT_PROVIDER_MODEL.items():
        env_key = f"TSB_LLM_MODEL_{provider.upper()}"
        keys.append(os.getenv(env_key) or fallback)
    return keys
