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

from core import ingest, llm, user_settings
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
    with st.sidebar:
        st.markdown("## ⚙ API 설정")
        if s.is_configured:
            st.success(f"연결 준비 완료\n\n- URL: `{s.api_base}`\n- Key: `{s.safe_api_key_preview()}`\n- Model: `{s.model}`")
        else:
            st.error("API URL과 키를 입력해야 스튜디오가 동작합니다.")

        with st.form("settings_form", clear_on_submit=False):
            api_base = st.text_input(
                "API 엔드포인트 URL",
                value=s.api_base,
                placeholder="예: https://llm.mycompany.com/v1",
                help="회사 LLM 게이트웨이 주소. /v1 은 자동으로 붙여드립니다. 공식 DeepSeek 사용 시: https://api.deepseek.com",
            )
            api_key = st.text_input(
                "API 키 (회사 발급)",
                value=s.api_key,
                type="password",
                placeholder="sk-...",
                help="키는 화면에 표시되지 않으며 data/user_settings.json 에 저장됩니다.",
            )
            model = st.text_input(
                "모델 이름",
                value=s.model or "deepseek-v4",
                placeholder="deepseek-v4",
                help="회사 게이트웨이가 사용하는 모델 식별자. 모르면 담당자에게 문의하세요.",
            )
            alt_models_str = st.text_input(
                "보조 모델 (선택, 콤마 구분)",
                value=", ".join(s.alt_models or []),
                placeholder="claude-opus-4-7, gpt-4o",
                help="여러 모델을 등록하면 작업 화면 상단 드롭다운에서 전환할 수 있습니다.",
            )
            col_a, col_b = st.columns(2)
            with col_a:
                temperature = st.number_input("Temperature", min_value=0.0, max_value=2.0, value=s.temperature, step=0.1)
            with col_b:
                max_tokens = st.number_input("Max Tokens", min_value=512, max_value=32000, value=s.max_tokens, step=512)

            col_save, col_test = st.columns(2)
            with col_save:
                save_btn = st.form_submit_button("💾 저장", use_container_width=True)
            with col_test:
                test_btn = st.form_submit_button("🔌 연결 테스트", use_container_width=True)

            if save_btn or test_btn:
                alt_models = [m.strip() for m in alt_models_str.split(",") if m.strip()]
                new_settings = user_settings.UserSettings(
                    api_base=api_base.strip(),
                    api_key=api_key.strip(),
                    model=model.strip() or "deepseek-v4",
                    temperature=float(temperature),
                    max_tokens=int(max_tokens),
                    alt_models=alt_models,
                )
                user_settings.save(new_settings)
                st.session_state["settings"] = new_settings

                if save_btn:
                    st.success("저장 완료")
                if test_btn:
                    with st.spinner("연결 테스트 중…"):
                        ok, msg = llm.test_connection(new_settings)
                    if ok:
                        st.success(f"연결 OK — {msg}")
                    else:
                        st.error(f"연결 실패 — {msg}")


# ---------- 사이드바: 출처 (소스 패널) ----------
def render_sources_panel(notebooks: list[str]) -> str | None:
    st.subheader("📚 출처")

    st.markdown("**노트북**")
    options = ["(새로 만들기)"] + notebooks
    selected = st.selectbox("노트북 선택", options=options, label_visibility="collapsed")

    notebook: str | None = None
    if selected == "(새로 만들기)":
        new_name = st.text_input("새 노트북 이름", placeholder="예: my-textbook-vol1")
        if st.button("➕ 노트북 생성", use_container_width=True):
            if new_name.strip():
                (DATA_DIR / slugify(new_name)).mkdir(parents=True, exist_ok=True)
                st.rerun()
    else:
        notebook = selected

    st.divider()

    if not notebook:
        st.info("먼저 노트북을 선택하거나 생성하세요.")
        return None

    st.markdown("**＋ 소스 추가**")
    uploaded = st.file_uploader(
        "Upload",
        type=["pdf", "txt", "md"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )
    if uploaded:
        registry = get_registry()
        for f in uploaded:
            sid = slugify(Path(f.name).stem)
            if sid in registry.sources:
                continue
            saved = save_uploaded(notebook, f)
            registry.add(sid, f.name, saved, active=True)
        st.success(f"{len(uploaded)}개 소스 등록")

    st.caption("200MB per file · PDF, TXT, MD")
    st.divider()

    st.markdown("**등록된 소스**")
    registry = get_registry()
    if registry.total_count == 0:
        st.caption("(없음)")
    else:
        for sid, entry in list(registry.sources.items()):
            cols = st.columns([1, 10])
            with cols[0]:
                new_state = st.checkbox(
                    "활성",
                    value=entry.active,
                    key=f"chk_{sid}",
                    label_visibility="collapsed",
                )
                if new_state != entry.active:
                    registry.set_active(sid, new_state)
                    st.rerun()
            with cols[1]:
                st.write(entry.filename)

        if st.button("등록 소스 모두 제거", use_container_width=True):
            reset_registry()
            st.rerun()

    return notebook


# ---------- 중앙: 채팅 + 스튜디오 ----------
def render_chat_and_studio(notebook: str) -> None:
    registry = get_registry()
    settings = get_settings()

    st.markdown(f"### 💬 채팅 — `{notebook}`  {registry.header_label()}")

    st.text_input(
        "질문하거나 창작하세요",
        placeholder="질문하거나 창작하세요  (채팅 기능은 후속 작업)",
        label_visibility="collapsed",
        disabled=True,
    )

    st.divider()

    # 모델 드롭다운 — 설정에서 등록된 모델 목록
    available_models = llm.list_available_models(settings)
    model = st.selectbox(
        "🛠 사용할 모델",
        options=available_models,
        index=0,
        help="좌측 ⚙ 설정에서 등록한 모델들. 기본 + 보조 모델.",
    )

    # 스튜디오 패널
    st.markdown("### 🧰 Studio")
    api_ready = settings.is_configured
    disabled_reason = registry.studio_disabled_reason()
    if not api_ready:
        st.warning("⚙ 좌측 설정 패널에서 API URL과 키를 먼저 입력하세요.")
    elif disabled_reason:
        st.warning(disabled_reason)

    studio_disabled = (disabled_reason is not None) or (not api_ready)

    cols = st.columns(2)
    for i, studio in enumerate(list_studios()):
        with cols[i % 2]:
            btn_label = f"{studio.icon}  {studio.label}"
            if st.button(
                btn_label,
                key=f"btn_{studio.key}",
                use_container_width=True,
                disabled=studio_disabled,
            ):
                _run_studio(notebook, model, studio)


def _run_studio(notebook: str, model: str, studio) -> None:
    registry = get_registry()
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
            model=model,
        )

        st.write(f"LLM 호출 (model={model})…")
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
    left, right = st.columns([1, 2], gap="large")
    with left:
        notebook = render_sources_panel(notebooks)
    with right:
        if notebook:
            render_chat_and_studio(notebook)
        else:
            st.info("좌측 패널에서 노트북을 선택하거나 생성하세요.")


if __name__ == "__main__":
    main()
