"""① 앞부속 (학습목표·학습내용·학습가이드) — 1버튼 통합, MD 출력."""
from __future__ import annotations

from core import llm, prompt_loader, chunker
from exporters import md_writer as md
from studio._base import StudioBase, StudioContext, StudioResult


class ChapterIntroStudio(StudioBase):
    key = "chapter_intro"
    label = "앞부속 (학습목표·내용·가이드)"
    icon = "📋"
    order = 1

    def run(self, ctx: StudioContext) -> StudioResult:
        body = chunker.fit_to_budget(ctx.body_text, budget_chars=60000)
        system, user = prompt_loader.render("chapter_intro_ko", body=body)
        data = llm.call_json(system, user, model=ctx.model)

        md_body = self._render_md(data)
        path = self.write_md(ctx, "chapter_intro.md", md_body)

        return StudioResult(
            studio=self.key,
            primary_path=path,
            summary=f"앞부속 생성 완료 — {data.get('chapter_title', '제목 미상')}",
        )

    def _render_md(self, data: dict) -> str:
        ch_no = data.get("chapter_no", 1)
        ch_title = (data.get("chapter_title") or "").strip()
        objectives = data.get("objectives") or []
        contents = data.get("contents") or []
        guide = data.get("guide") or []

        title = f"제{ch_no}장 {ch_title}" if ch_title else f"제{ch_no}장"

        return md.join(
            md.h1(title),
            md.h2("학습목표"),
            md.bullets(objectives),
            md.h2("학습내용"),
            md.bullets(contents),
            md.h2("학습가이드"),
            md.bullets(guide),
        )
