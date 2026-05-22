"""TSBookMaker — Streamlit 3-panel UI.

원본 local-notebooklm 의 UX 를 차용하되:
- 5개 스튜디오 버튼만 노출
- "소스 N개" 카운트 버그 수정 — 활성 소스만 카운트, 0개 시 버튼 비활성화
- ⚙ 설정 패널 — 교수자가 API URL/Key/모델명을 GUI 에서 직접 입력·저장
"""
from __future__ import annotations

import os
import re
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from core import ingest, llm, rag, user_settings
from core.source_state import SourceRegistry
from studio import list_studios
from studio._base import StudioContext

# ---------- 부트스트랩 ----------
load_dotenv()

DATA_DIR = Path(os.getenv("TSB_DATA_DIR", "./data/notebooks")).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="TSBookMaker", page_icon="📚", layout="wide")


# ---------- 헬퍼 ----------
def list_notebooks() -> list[str]:
    return sorted([p.name for p in DATA_DIR.iterdir() if p.is_dir()])


def get_registry() -> SourceRegistry:
    if "registry" not in st.session_state:
        st.session_state["registry"] = SourceRegistry()
    return st.session_state["registry"]


def reset_registry() -> None:
    st.session_state["registry"] = SourceRegistry()


def get_settings() -> user_settings.UserSettings:
    if "settings" not in st.session_state:
        st.session_state["settings"] = user_settings.load()
    return st.session_state["settings"]


def slugify(name: str) -> str:
    base = re.sub(r"[^\w\-가-힣]+", "_", name.strip())
    return base.strip("_") or f"src-{uuid.uuid4().hex[:8]}"


def detect_chapter_hint(filenames: list[str]) -> str:
    if len(filenames) == 1:
        m = re.search(r"(\d{1,3})", filenames[0])
        if m:
            return f"ch{int(m.group(1)):02d}"
        return Path(filenames[0]).stem[:24]
    return f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def save_uploaded(notebook: str, uploaded_file) -> Path:
    sources_dir = DATA_DIR / notebook / "_sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    target = sources_dir / uploaded_file.name
    target.write_bytes(uploaded_file.getbuffer())
    return target


# ---------- ⚙ 설정 패널 ----------
def render_settings_panel() -> None:
    s = get_settings()
    show_presets = os.getenv("TSB_SHOW_PRESETS", "1") != "0"

    with st.sidebar:
        st.markdown("## ⚙ API 설정")
        if s.is_configured:
            st.success(
                "연결 준비 완료\n\n"
                f"- URL: `{s.api_base}`\n"
                f"- Key: `{s.safe_api_key_preview()}`\n"
                f"- 모델: {s.preset_label()}"
            )
        else:
            st.error("URL과 API 키를 입력하세요.")

        # URL / 키 — 단순 입력 (폼 밖, 즉시 반영)
        api_base = st.text_input(
            "API URL",
            value=s.api_base,
            placeholder="http://192.168.50.119:4000",
            help="사내 LiteLLM 게이트웨이 주소. /v1 은 자동으로 붙습니다.",
        )
        api_key = st.text_input(
            "API 키",
            value=s.api_key,
            type="password",
            placeholder="sk-...",
            help="회사에서 발급받은 키. data/user_settings.json 에만 저장됩니다.",
        )

        # 프리셋 버튼 (TSB_SHOW_PRESETS=0 환경변수로 숨김 가능)
        if show_presets:
            st.markdown("**모델 프리셋**")
            preset_keys = list(user_settings.PRESETS.keys())
            cols = st.columns(len(preset_keys))
            for i, key in enumerate(preset_keys):
                preset = user_settings.PRESETS[key]
                with cols[i]:
                    is_current = (s.preset == key)
                    btn = st.button(
                        preset["label"],
                        key=f"preset_{key}",
                        use_container_width=True,
                        type=("primary" if is_current else "secondary"),
                    )
                    if btn:
                        new_settings = user_settings.UserSettings(
                            api_base=api_base.strip(),
                            api_key=api_key.strip(),
                            preset=key,
                            model=user_settings.preset_to_model(key),
                            temperature=s.temperature,
                            max_tokens=s.max_tokens,
                        )
                        user_settings.save(new_settings)
                        st.session_state["settings"] = new_settings
                        st.rerun()
            st.caption(user_settings.PRESETS[s.preset]["desc"])

        # 고급 (접힘)
        with st.expander("고급 설정", expanded=False):
            temperature = st.number_input(
                "Temperature", min_value=0.0, max_value=2.0, value=s.temperature, step=0.1
            )
            max_tokens = st.number_input(
                "Max Tokens", min_value=512, max_value=32000, value=s.max_tokens, step=512
            )

        col_save, col_test = st.columns(2)
        with col_save:
            if st.button("💾 저장", use_container_width=True, key="settings_save"):
                new_settings = user_settings.UserSettings(
                    api_base=api_base.strip(),
                    api_key=api_key.strip(),
                    preset=s.preset,
                    model=user_settings.preset_to_model(s.preset),
                    temperature=float(temperature),
                    max_tokens=int(max_tokens),
                )
                user_settings.save(new_settings)
                st.session_state["settings"] = new_settings
                st.success("저장 완료")
                st.rerun()
        with col_test:
            if st.button("🔌 연결 테스트", use_container_width=True, key="settings_test"):
                test_settings = user_settings.UserSettings(
                    api_base=api_base.strip(),
                    api_key=api_key.strip(),
                    preset=s.preset,
                    model=user_settings.preset_to_model(s.preset),
                    temperature=float(temperature),
                    max_tokens=int(max_tokens),
                )
                with st.spinner("연결 테스트 중…"):
                    ok, msg = llm.test_connection(test_settings)
                if ok:
                    st.success(f"연결 OK — {msg}")
                else:
                    st.error(f"연결 실패 — {msg}")


# ---------- 우측(narrow): 출처 패널 ----------
def render_sources_panel(notebooks: list[str]) -> str | None:
    st.markdown("### 📚 출처")

    options = ["(새로 만들기)"] + notebooks
    selected = st.selectbox(
        "노트북",
        options=options,
        label_visibility="visible",
    )

    notebook: str | None = None
    if selected == "(새로 만들기)":
        new_name = st.text_input("새 노트북 이름", placeholder="예: my-vol1")
        if st.button("➕ 생성", use_container_width=True):
            if new_name.strip():
                (DATA_DIR / slugify(new_name)).mkdir(parents=True, exist_ok=True)
                st.rerun()
        return None
    notebook = selected

    uploaded = st.file_uploader(
        "＋ 소스 추가",
        type=["pdf", "txt", "md", "hwpx"],
        accept_multiple_files=True,
    )
    if uploaded:
        registry = get_registry()
        settings = get_settings()
        to_index: list[tuple[str, Path]] = []
        for f in uploaded:
            sid = slugify(Path(f.name).stem)
            if sid in registry.sources:
                continue
            saved = save_uploaded(notebook, f)
            registry.add(sid, f.name, saved, active=True)
            to_index.append((f.name, saved))

        if to_index and settings.is_configured:
            with st.status(f"인덱싱 중 ({len(to_index)}개) — 챕터당 30초~2분", expanded=True) as status:
                for fname, path in to_index:
                    st.write(f"⏳ {fname}")
                    result = rag.index_source_sync(notebook, path, settings=settings)
                    if result["ok"]:
                        st.write(f"✓ {fname}  ({result['took_sec']:.1f}s)")
                    else:
                        st.write(f"⚠ {fname} 실패: {result.get('error')}")
                status.update(label="인덱싱 완료", state="complete")
        elif to_index:
            st.warning(
                "⚙ API 설정이 비어 있어 인덱싱이 보류됐습니다. "
                "URL/키 입력 후 [등록된 소스] 옆 ⟳ 버튼으로 다시 시도하세요."
            )
        st.success(f"{len(uploaded)}개 등록")

    st.markdown("**등록된 소스**")
    registry = get_registry()
    if registry.total_count == 0:
        st.caption("(없음)")
    else:
        for sid, entry in list(registry.sources.items()):
            new_state = st.checkbox(
                entry.filename,
                value=entry.active,
                key=f"chk_{sid}",
            )
            if new_state != entry.active:
                registry.set_active(sid, new_state)
                st.rerun()

        if st.button("모두 제거", use_container_width=True):
            reset_registry()
            st.rerun()

    return notebook


# ---------- 좌측: 스튜디오 패널 ----------
def render_studio_panel(notebook: str) -> None:
    registry = get_registry()
    settings = get_settings()

    st.markdown("### 🧰 Studio")

    api_ready = settings.is_configured
    disabled_reason = registry.studio_disabled_reason()
    if not api_ready:
        st.warning("⚙ 좌측 사이드바에서 API URL/키를 먼저 입력하세요.")
    elif disabled_reason:
        st.warning(disabled_reason)

    studio_disabled = (disabled_reason is not None) or (not api_ready)

    # 세로 배치 — 좁은 좌측 컬럼에 1열로 5버튼
    for studio in list_studios():
        btn_label = f"{studio.icon}  {studio.label}"
        if st.button(
            btn_label,
            key=f"btn_{studio.key}",
            use_container_width=True,
            disabled=studio_disabled,
        ):
            st.session_state["pending_studio"] = studio.key
            st.rerun()


# ---------- 중앙: 채팅 + 실행 결과 ----------
def render_chat_panel(notebook: str) -> None:
    registry = get_registry()
    settings = get_settings()

    st.markdown(f"### 💬 채팅 — `{notebook}`  {registry.header_label()}")

    # 채팅 히스토리 (노트북별)
    hist_key = f"chat_history::{notebook}"
    history = st.session_state.setdefault(hist_key, [])

    for msg in history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    api_ready = settings.is_configured
    has_index = rag.has_index(notebook)

    placeholder = (
        "질문을 입력하세요 (예: 은퇴 준비기와 후기 고령기의 핵심 차이를 표로 정리해줘)"
        if (api_ready and has_index)
        else (
            "⚙ 설정에서 API URL/키를 먼저 입력하세요" if not api_ready
            else "소스를 업로드하고 인덱싱이 끝나야 채팅이 가능합니다"
        )
    )

    prompt = st.chat_input(placeholder, disabled=not (api_ready and has_index))
    if prompt:
        history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("검색 + 답변 생성 중…"):
                try:
                    response = rag.query_sync(notebook, prompt, settings=settings)
                except Exception as ex:  # noqa: BLE001
                    response = f"오류: {type(ex).__name__} — {ex}"
            st.markdown(response)
        history.append({"role": "assistant", "content": response})

    # 스튜디오 실행 결과 자리 — 좌측 버튼이 눌리면 여기에 결과 표시
    pending = st.session_state.pop("pending_studio", None)
    if pending:
        from studio import get_studio
        st.divider()
        _run_studio(notebook, get_studio(pending))

    # 직전 실행 산출물(있다면) 다시 보여주기 위해 session_state 에 보관
    last = st.session_state.get("last_result")
    if last and not pending:
        st.divider()
        st.caption(f"최근 실행: {last['studio']} — {last['summary']}")
        for p_str in last["paths"]:
            p = Path(p_str)
            st.write(f"📄 `{p.name}`")
            if p.suffix == ".md" and p.exists():
                with st.expander(f"미리보기 — {p.name}"):
                    st.markdown(p.read_text(encoding="utf-8"))


def _run_studio(notebook: str, studio) -> None:
    registry = get_registry()
    settings = get_settings()
    active_entries = registry.active_sources()
    if not active_entries:
        st.error("활성 소스가 없습니다.")
        return

    with st.status(f"{studio.label} 실행 중…", expanded=True) as status:
        st.write(f"활성 소스: {[e.filename for e in active_entries]}")
        docs = []
        for e in active_entries:
            try:
                docs.append(ingest.ingest_any(e.path, source_id=e.source_id))
            except Exception as ex:  # noqa: BLE001
                status.update(label=f"{studio.label} 실패 — 인제스트 오류", state="error")
                st.error(f"인제스트 실패 — {e.filename}: {ex}")
                return
        body_text = ingest.merge_docs(docs)
        st.write(f"본문 길이: {len(body_text):,} 자")

        chapter_hint = detect_chapter_hint([e.filename for e in active_entries])
        output_dir = DATA_DIR / notebook / chapter_hint
        output_dir.mkdir(parents=True, exist_ok=True)

        ctx = StudioContext(
            body_text=body_text,
            output_dir=output_dir,
            notebook_id=notebook,
            chapter_hint=chapter_hint,
            model=None,  # 설정의 디폴트 모델 사용
        )

        st.write(f"LLM 호출 (model={settings.model})…")
        try:
            result = studio.run(ctx)
        except llm.LLMConfigError as ex:
            status.update(label=f"{studio.label} 실패 — API 설정 오류", state="error")
            st.error(str(ex))
            return
        except Exception as ex:  # noqa: BLE001
            status.update(label=f"{studio.label} 실패", state="error")
            st.exception(ex)
            return

        status.update(label=f"{studio.label} 완료", state="complete")
        st.success(result.summary)
        st.session_state["last_result"] = {
            "studio": studio.label,
            "summary": result.summary,
            "paths": [str(p) for p in result.all_paths()],
        }
        for p in result.all_paths():
            try:
                rel = p.relative_to(DATA_DIR.parent)
            except ValueError:
                rel = p
            st.write(f"📄 `{rel}`")
            if p.suffix == ".md":
                with st.expander(f"미리보기 — {p.name}"):
                    st.markdown(p.read_text(encoding="utf-8"))


# ---------- 메인 ----------
def main() -> None:
    # ⚙ 설정 패널 — 사이드바에 항상 노출
    render_settings_panel()

    notebooks = list_notebooks()

    # 3-column: 스튜디오(좌, 좁음) · 채팅(중, 넓음) · 출처(우, narrow)
    studio_col, chat_col, source_col = st.columns([1.3, 2.6, 1.2], gap="medium")

    with source_col:
        notebook = render_sources_panel(notebooks)

    with studio_col:
        if notebook:
            render_studio_panel(notebook)
        else:
            st.markdown("### 🧰 Studio")
            st.caption("우측에서 노트북을 선택하세요.")

    with chat_col:
        if notebook:
            render_chat_panel(notebook)
        else:
            st.info("우측 출처 패널에서 노트북을 선택하거나 생성하세요.")


if __name__ == "__main__":
    main()
