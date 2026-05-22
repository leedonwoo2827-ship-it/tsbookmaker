"""⑤ 30매 슬라이드 교안 (텍스트) — GPTs/Gemini Canvas 입력용 MD."""
from __future__ import annotations

import os

from core import llm, prompt_loader, chunker
from exporters import md_writer as md
from studio._base import StudioBase, StudioContext, StudioResult


class SlideDeckStudio(StudioBase):
    key = "slide_deck"
    label = "슬라이드 교안 (30매)"
    icon = "📊"
    order = 5

    def run(self, ctx: StudioContext) -> StudioResult:
        slide_count = int(os.getenv("TSB_SLIDE_COUNT", "30"))

        body = chunker.fit_to_budget(ctx.body_text, budget_chars=80000)
        system, user = prompt_loader.render(
            "slide_deck_ko",
            body=body,
            slide_count=slide_count,
        )
        data = llm.call_json(system, user, model=ctx.model)
        slides = data.get("slides") or []
        deck_title = (data.get("deck_title") or "").strip()
        duration = data.get("duration_min", 50)

        md_body = self._render_md(deck_title, duration, slides)
        path = self.write_md(ctx, "slide_deck.md", md_body)

        return StudioResult(
            studio=self.key,
            primary_path=path,
            summary=f"슬라이드 교안 생성 완료 — {len(slides)}매",
        )

    def _render_md(self, deck_title: str, duration: int, slides: list[dict]) -> str:
        blocks: list[str] = []
        title = deck_title or "슬라이드 교안"
        blocks.append(md.h1(title))
        blocks.append(md.paragraph(f"_총 {len(slides)}매 · 강의 시간 약 {duration}분_"))

        for s in slides:
            no = s.get("no", "")
            section = (s.get("section") or "").strip()
            stitle = (s.get("title") or "").strip()
            bullets = s.get("bullets") or []
            notes = (s.get("notes") or "").strip()

            heading = f"Slide {no} — {stitle}"
            if section:
                heading = f"{heading}  _[{section}]_"
            blocks.append(md.h2(heading))
            if bullets:
                blocks.append(md.bullets(bullets))
            if notes:
                blocks.append(f"> notes: {notes}\n")

        return md.join(*blocks)
