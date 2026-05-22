"""프롬프트 파일 로더. `prompts/*_ko.md` 를 읽어 system/user 템플릿으로 분리."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

# 프롬프트 파일은 다음 구분자로 system / user 를 나눈다:
#   <<SYSTEM>>
#   ...system text...
#   <<USER>>
#   ...user text with {placeholders}...
SYSTEM_MARK = "<<SYSTEM>>"
USER_MARK = "<<USER>>"


@lru_cache(maxsize=64)
def load(name: str) -> tuple[str, str]:
    """이름(예: 'chapter_intro_ko')에 해당하는 .md 파일을 읽어 (system, user_template) 반환."""
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"프롬프트 파일을 찾을 수 없음: {path}")
    raw = path.read_text(encoding="utf-8")

    if SYSTEM_MARK not in raw or USER_MARK not in raw:
        raise ValueError(f"{path.name} 에 {SYSTEM_MARK} / {USER_MARK} 구분자가 누락되었습니다.")

    sys_part = raw.split(SYSTEM_MARK, 1)[1]
    sys_text, user_part = sys_part.split(USER_MARK, 1)
    return sys_text.strip(), user_part.strip()


def render(name: str, **kwargs) -> tuple[str, str]:
    """프롬프트를 로드하고 user 템플릿에 변수를 치환해서 반환."""
    system, user_tmpl = load(name)
    try:
        user = user_tmpl.format(**kwargs)
    except KeyError as e:
        raise KeyError(f"프롬프트 {name} 의 user 템플릿에 누락된 변수: {e}") from e
    return system, user
