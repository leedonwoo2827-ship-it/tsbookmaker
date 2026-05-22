"""RAG-Anything 래퍼 — 노트북별로 인덱스 + 검색 제공.

설계 원칙
- LLM 호출은 사용자가 ⚙ 설정에서 등록한 회사 LiteLLM 게이트웨이로 라우팅.
  raganything 가 OpenAI 호환 콜백을 받아주므로 lightrag 의 `openai_complete_if_cache`
  를 그대로 사용한다.
- 임베딩은 로컬 BGE-M3 (sentence-transformers). 첫 호출 시 HuggingFace 캐시에
  ~2.3GB 다운로드. 두 번째부터는 즉시 로드.
- 인덱스는 노트북별로 격리: `data/notebooks/<책>/rag_storage/`. 노트북 안의
  여러 소스(챕터)는 동일 인덱스에 함께 쌓여 책 전체 검색을 가능하게 한다.
- OCR 비활성: `enable_image_processing=False` + `parse_method="txt"`.
"""
from __future__ import annotations

import asyncio
import os
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from core import user_settings
from core.user_settings import UserSettings


DATA_DIR = Path(os.getenv("TSB_DATA_DIR", "./data/notebooks")).resolve()


# ---------------------------------------------------------------------------
# 임베딩 — 로컬 BGE-M3 (sentence-transformers)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _embed_model():
    """BGE-M3 임베딩 모델을 1회 로드해 캐시."""
    from sentence_transformers import SentenceTransformer

    model_name = os.getenv("TSB_EMBED_MODEL", "BAAI/bge-m3")
    device = os.getenv("TSB_EMBED_DEVICE", "cpu")
    return SentenceTransformer(model_name, device=device)


async def _embed(texts: list[str]) -> np.ndarray:
    model = _embed_model()
    # SentenceTransformer.encode 는 동기 → 이벤트 루프 차단 방지를 위해 to_thread
    vecs = await asyncio.to_thread(
        model.encode,
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return np.asarray(vecs, dtype=np.float32)


def _embedding_dim() -> int:
    return _embed_model().get_sentence_embedding_dimension() or 1024


# ---------------------------------------------------------------------------
# LLM 콜백 — ⚙ 설정의 회사 LiteLLM 게이트웨이로 라우팅
# ---------------------------------------------------------------------------
def _build_llm_func(settings: UserSettings):
    """raganything 가 호출할 LLM 콜백을 만든다. 매번 settings 로 새 콜백 생성."""
    from lightrag.llm.openai import openai_complete_if_cache

    base_url = settings.api_base.rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = base_url + "/v1"

    async def llm_func(prompt, system_prompt=None, history_messages=None, **kwargs):
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
# RAGAnything 인스턴스 — 노트북별 캐시
# ---------------------------------------------------------------------------
_RAG_CACHE: dict[str, Any] = {}


def _working_dir(notebook: str) -> Path:
    return DATA_DIR / notebook / "rag_storage"


def get_rag(notebook: str, settings: UserSettings | None = None):
    """노트북별 RAGAnything 인스턴스. 같은 노트북은 재사용."""
    from lightrag.utils import EmbeddingFunc
    from raganything import RAGAnything, RAGAnythingConfig

    s = settings or user_settings.load()
    if notebook in _RAG_CACHE:
        return _RAG_CACHE[notebook]

    work = _working_dir(notebook)
    work.mkdir(parents=True, exist_ok=True)

    config = RAGAnythingConfig(
        working_dir=str(work),
        parser="mineru",
        parse_method="txt",
        enable_image_processing=False,
        enable_table_processing=False,
        enable_equation_processing=False,
    )

    rag = RAGAnything(
        config=config,
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
    """모델/설정 변경 후 캐시된 인스턴스를 폐기."""
    if notebook is None:
        _RAG_CACHE.clear()
    else:
        _RAG_CACHE.pop(notebook, None)


# ---------------------------------------------------------------------------
# 인덱싱
# ---------------------------------------------------------------------------
async def index_source(
    notebook: str,
    source_path: str | Path,
    *,
    settings: UserSettings | None = None,
) -> dict:
    """단일 소스 파일(PDF/TXT/MD/HWPX)을 인덱싱.

    반환: {ok: bool, took_sec: float, error?: str}
    """
    p = Path(source_path)
    start = time.monotonic()
    try:
        rag = get_rag(notebook, settings=settings)
        await rag.process_document_complete(
            file_path=str(p),
            output_dir=str(_working_dir(notebook) / "_parsed"),
            parse_method="txt",
            parser="mineru",
        )
        return {"ok": True, "took_sec": time.monotonic() - start}
    except Exception as ex:  # noqa: BLE001
        return {
            "ok": False,
            "took_sec": time.monotonic() - start,
            "error": f"{type(ex).__name__}: {ex}",
        }


def index_source_sync(notebook: str, source_path: str | Path, **kwargs) -> dict:
    """Streamlit 에서 부르기 좋은 동기 래퍼."""
    return asyncio.run(index_source(notebook, source_path, **kwargs))


def is_indexed(notebook: str, source_filename: str) -> bool:
    """간단 체크 — 인덱스 폴더에 해당 파일 흔적이 있나."""
    parsed_dir = _working_dir(notebook) / "_parsed"
    if not parsed_dir.exists():
        return False
    stem = Path(source_filename).stem
    return any(stem in p.name for p in parsed_dir.rglob("*"))


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
    """노트북에 인덱싱된 소스를 기반으로 답한다."""
    rag = get_rag(notebook, settings=settings)
    q_mode = mode or os.getenv("TSB_RAG_QUERY_MODE", "hybrid")
    top_k = int(os.getenv("TSB_RAG_TOP_K", "10"))
    return await rag.aquery(prompt, mode=q_mode, top_k=top_k)


def query_sync(notebook: str, prompt: str, **kwargs) -> str:
    return asyncio.run(query(notebook, prompt, **kwargs))


def has_index(notebook: str) -> bool:
    work = _working_dir(notebook)
    if not work.exists():
        return False
    # LightRAG 가 생성하는 시그니처 파일 중 하나라도 있으면 인덱스 존재
    sentinels = [
        "kv_store_full_docs.json",
        "kv_store_text_chunks.json",
        "vdb_chunks.json",
    ]
    return any((work / s).exists() for s in sentinels)
