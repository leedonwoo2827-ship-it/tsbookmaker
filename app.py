"""TSBookMaker — Streamlit 3-panel UI.

원본 local-notebooklm 의 UX 를 차용하되:
- 5개 스튜디오 버튼만 노출
- "소스 N개" 카운트 버그 수정 — 활성 소스만 카운트, 0개 시 버튼 비활성화
- 모델 드롭다운 (DeepSeek V4 디폴트)
"""
from __future__ import annotations

import os
import re
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from core import ingest, llm
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


def slugify(name: str) -> str:
    base = re.sub(r"[^\w\-가-힣]+", "_", name.strip())
    return base.strip("_") or f"src-{uuid.uuid4().hex[:8]}"


def detect_chapter_hint(filenames: list[str]) -> str:
    """파일명에서 챕터 힌트를 추출 (ch01, 01장, 17-43 등). 실패 시 timestamp."""
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


# ---------- 사이드바: 출처 (소스 패널) ----------
def render_sources_panel(notebooks: list[str]) -> str | None:
    st.subheader("📚 출처")

    # 노트북 선택
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

    # 소스 업로드
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

    # 등록된 소스 목록 + 체크박스
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

    # 채팅 헤더 — 버그 수정된 카운트 라벨
    st.markdown(
        f"### 💬 채팅 — `{notebook}`  {registry.header_label()}"
    )

    # 채팅 입력 (스튜디오 작업과 별개, RAG 채팅은 후속 작업)
    st.text_input(
        "질문하거나 창작하세요",
        placeholder="질문하거나 창작하세요  (채팅 기능은 후속 작업)",
        label_visibility="collapsed",
        disabled=True,
    )

    st.divider()

    # 모델 드롭다운
    available_models = llm.list_available_models()
    default_model = available_models[0] if available_models else "deepseek-v4"
    model = st.selectbox(
        "🛠 LLM 모델",
        options=available_models,
        index=0,
        help="디폴트 DeepSeek V4. 품질이 더 필요하면 Claude Opus 4.7 / GPT-4o 로 전환.",
    )

    # 스튜디오 패널
    st.markdown("### 🧰 Studio")
    disabled_reason = registry.studio_disabled_reason()
    if disabled_reason:
        st.warning(disabled_reason)

    cols = st.columns(2)
    for i, studio in enumerate(list_studios()):
        with cols[i % 2]:
            btn_label = f"{studio.icon}  {studio.label}"
            if st.button(
                btn_label,
                key=f"btn_{studio.key}",
                use_container_width=True,
                disabled=disabled_reason is not None,
            ):
                _run_studio(notebook, model, studio)


def _run_studio(notebook: str, model: str, studio) -> None:
    registry = get_registry()
    active_entries = registry.active_sources()
    if not active_entries:
        st.error("활성 소스가 없습니다.")
        return

    # 본문 인제스트 + 병합
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

        # 출력 경로
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
        except Exception as ex:  # noqa: BLE001
            status.update(label=f"{studio.label} 실패", state="error")
            st.exception(ex)
            return

        status.update(label=f"{studio.label} 완료", state="complete")
        st.success(result.summary)
        for p in result.all_paths():
            st.write(f"📄 `{p.relative_to(DATA_DIR.parent) if DATA_DIR.parent in p.parents else p}`")
            if p.suffix == ".md":
                with st.expander(f"미리보기 — {p.name}"):
                    st.markdown(p.read_text(encoding="utf-8"))


# ---------- 메인 ----------
def main() -> None:
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
