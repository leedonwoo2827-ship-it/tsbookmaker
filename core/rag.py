"""LightRAG 기반 채팅 인덱스 — raganything 의 PDF 파서 우회.

설계 원칙
- 텍스트 추출은 우리 `core/ingest.py` (pymupdf + HWPX) 가 담당. raganything 의
  process_document_complete (mineru 등 별도 파서 요구) 를 거치지 않는다.
- LLM 호출은 사용자가 ⚙ 설정에서 등록한 회사 LiteLLM 게이트웨이로 라우팅.
  lightrag 의 `openai_complete_if_cache` 가 OpenAI 호환 콜백을 제공.
- 임베딩은 로컬 BGE-M3 (sentence-transformers). 첫 호출 시 HuggingFace 캐시에
  ~2.3GB 다운로드, 이후 즉시 로드.
- 인덱스는 노트북별로 격리: `data/notebooks/<책>/rag_storage/`. 한 노트북 안의
  여러 소스(챕터)는 같은 인덱스에 쌓여 책 전체 검색 가능.
- 페이지 메타: ingest.IngestedDoc.full_text 가 `[p.N]\n...` 형식으로 묶어
  보내므로 LightRAG 가 chunk 안에 페이지 prefix 를 자연스럽게 보존한다.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from core import ingest, user_settings
from core.user_settings import UserSettings


DATA_DIR = Path(os.getenv("TSB_DATA_DIR", "./data/notebooks")).resolve()


def _log(msg: str) -> None:
    """Streamlit 의 status 박스가 가려도 PS 터미널에서 볼 수 있도록 stderr 에도 출력."""
    print(f"[rag] {msg}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# 임베딩 — 로컬 BGE-M3 (sentence-transformers)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _embed_model():
    from sentence_transformers import SentenceTransformer

    model_name = os.getenv("TSB_EMBED_MODEL", "BAAI/bge-m3")
    device = os.getenv("TSB_EMBED_DEVICE", "cpu")
    _log(f"임베딩 모델 로드 시작: {model_name} (device={device})")
    m = SentenceTransformer(model_name, device=device)
    _log(f"임베딩 모델 로드 완료 (dim={m.get_sentence_embedding_dimension()})")
    return m


async def _embed(texts: list[str]) -> np.ndarray:
    model = _embed_model()
    vecs = await asyncio.to_thread(
        model.encode,
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return np.asarray(vecs, dtype=np.float32)


def _embedding_dim() -> int:
    m = _embed_model()
    # sentence-transformers 3.x 부터 get_embedding_dimension 권장 (구버전 호환 fallback)
    if hasattr(m, "get_embedding_dimension"):
        return m.get_embedding_dimension() or 1024
    return m.get_sentence_embedding_dimension() or 1024


# ---------------------------------------------------------------------------
# LLM 콜백 — ⚙ 설정의 회사 LiteLLM 게이트웨이로 라우팅
# ---------------------------------------------------------------------------
def _build_llm_func(settings: UserSettings):
    from lightrag.llm.openai import openai_complete_if_cache

    base_url = settings.api_base.rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = base_url + "/v1"

    async def llm_func(prompt, system_prompt=None, history_messages=None, **kwargs):
        # raganything/lightrag 가 keyword_extraction 등 우리가 지원 안 하는 kwarg 를
        # 넘길 수 있으니 알려진 것만 추리고 나머지는 버린다.
        kwargs.pop("keyword_extraction", None)
        kwargs.pop("hashing_kv", None)
        return await openai_complete_if_cache(
            settings.model,
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages or [],
            api_key=settings.api_key,
            base_url=base_url,
            **kwargs,
        )

    return llm_func


# ---------------------------------------------------------------------------
# LightRAG 인스턴스 — 노트북별 캐시
# ---------------------------------------------------------------------------
_RAG_CACHE: dict[str, Any] = {}


def _working_dir(notebook: str) -> Path:
    return DATA_DIR / notebook / "rag_storage"


def get_rag(notebook: str, settings: UserSettings | None = None):
    from lightrag import LightRAG
    from lightrag.utils import EmbeddingFunc

    s = settings or user_settings.load()
    if notebook in _RAG_CACHE:
        return _RAG_CACHE[notebook]

    work = _working_dir(notebook)
    work.mkdir(parents=True, exist_ok=True)

    _log(f"LightRAG 인스턴스 생성: notebook={notebook} dir={work}")
    rag = LightRAG(
        working_dir=str(work),
        llm_model_func=_build_llm_func(s),
        embedding_func=EmbeddingFunc(
            embedding_dim=_embedding_dim(),
            max_token_size=8192,
            func=_embed,
        ),
    )
    _RAG_CACHE[notebook] = rag
    return rag


def reset(notebook: str | None = None) -> None:
    if notebook is None:
        _RAG_CACHE.clear()
    else:
        _RAG_CACHE.pop(notebook, None)


# ---------------------------------------------------------------------------
# 인덱싱 — ingest.py 로 텍스트 뽑고 LightRAG 에 넣기
# ---------------------------------------------------------------------------
async def index_source(
    notebook: str,
    source_path: str | Path,
    *,
    settings: UserSettings | None = None,
) -> dict:
    """단일 소스(PDF/TXT/MD/HWPX)를 텍스트 추출 후 LightRAG 에 insert."""
    p = Path(source_path)
    start = time.monotonic()
    try:
        _log(f"인덱싱 시작: {p.name}")
        doc = ingest.ingest_any(p)
        # ingest 가 페이지별 prefix `[p.N]` 를 붙여서 full_text 반환
        text = doc.full_text
        if not text.strip():
            return {"ok": False, "took_sec": 0, "error": "본문이 비어있음"}

        rag = get_rag(notebook, settings=settings)
        _log(f"  → 텍스트 {len(text):,}자 추출, LightRAG insert 시작")
        await rag.ainsert(text, ids=p.stem)
        took = time.monotonic() - start
        _log(f"인덱싱 완료: {p.name} ({took:.1f}s)")
        return {"ok": True, "took_sec": took, "chars": len(text), "pages": doc.page_count}
    except Exception as ex:  # noqa: BLE001
        took = time.monotonic() - start
        msg = f"{type(ex).__name__}: {ex}"
        _log(f"인덱싱 실패: {p.name} — {msg}")
        return {"ok": False, "took_sec": took, "error": msg}


def index_source_sync(notebook: str, source_path: str | Path, **kwargs) -> dict:
    return asyncio.run(index_source(notebook, source_path, **kwargs))


# ---------------------------------------------------------------------------
# 쿼리
# ---------------------------------------------------------------------------
async def query(
    notebook: str,
    prompt: str,
    *,
    mode: str | None = None,
    settings: UserSettings | None = None,
) -> str:
    from lightrag import QueryParam

    rag = get_rag(notebook, settings=settings)
    q_mode = mode or os.getenv("TSB_RAG_QUERY_MODE", "hybrid")
    top_k = int(os.getenv("TSB_RAG_TOP_K", "10"))
    _log(f"쿼리: mode={q_mode} top_k={top_k} prompt={prompt[:60]}...")
    return await rag.aquery(prompt, param=QueryParam(mode=q_mode, top_k=top_k))


def query_sync(notebook: str, prompt: str, **kwargs) -> str:
    return asyncio.run(query(notebook, prompt, **kwargs))


def has_index(notebook: str) -> bool:
    work = _working_dir(notebook)
    if not work.exists():
        return False
    sentinels = [
        "kv_store_full_docs.json",
        "kv_store_text_chunks.json",
        "vdb_chunks.json",
    ]
    return any((work / s).exists() for s in sentinels)
