"""② 단원학습정리 — 체크리스트 표 + I/II/III 본문 + 핵심 정리 + 도식."""
from __future__ import annotations

from core import llm, prompt_loader, chunker
from exporters import md_writer as md
from studio._base import StudioBase, StudioContext, StudioResult


class ChapterSummaryStudio(StudioBase):
    key = "chapter_summary"
    label = "단원학습정리"
    icon = "📝"
    order = 2

    def run(self, ctx: StudioContext) -> StudioResult:
        body = chunker.fit_to_budget(ctx.body_text, budget_chars=80000)
        system, user = prompt_loader.render("chapter_summary_ko", body=body)
        data = llm.call_json(system, user, model=ctx.model)

        md_body = self._render_md(data)
        path = self.write_md(ctx, "chapter_summary.md", md_body)

        return StudioResult(
            studio=self.key,
            primary_path=path,
            summary="단원학습정리 생성 완료",
        )

    def _render_md(self, data: dict) -> str:
        blocks: list[str] = [md.h1("단원학습정리")]

        # 1. 체크리스트 표
        checklist = data.get("checklist") or {}
        headers = checklist.get("headers") or ["역량 영역", "구체적 역량", "실천 방법"]
        rows = checklist.get("rows") or []
        if rows:
            blocks.append(md.h2("표 1. 핵심 역량 체크리스트"))
            blocks.append(md.gfm_table(headers, rows))

        # 2. 본문 I/II/III
        body_sections = data.get("body") or []
        for sec in body_sections:
            roman = (sec.get("roman") or "").strip()
            title = (sec.get("title") or "").strip()
            heading = f"{roman}. {title}" if roman and title else (title or roman)
            blocks.append(md.h2(heading))
            intro = (sec.get("intro") or "").strip()
            if intro:
                blocks.append(md.paragraph(intro))
            for item in sec.get("items") or []:
                no = item.get("no", "")
                subtitle = (item.get("subtitle") or "").strip()
                item_body = (item.get("body") or "").strip()
                head = f"{no}. {subtitle}".strip(". ").strip()
                if head:
                    blocks.append(md.h3(head))
                if item_body:
                    blocks.append(md.paragraph(item_body))

        # 3. 핵심 정리
        takeaways = data.get("key_takeaways") or []
        if takeaways:
            blocks.append(md.h2("핵심 정리"))
            blocks.append(md.numbered(takeaways))

        # 4. 도식 (텍스트)
        diagram = data.get("diagram") or {}
        stages = diagram.get("stages") or []
        if stages:
            title = (diagram.get("title") or "핵심 요소 흐름").strip()
            blocks.append(md.h2(f"도식: {title}"))
            blocks.append(md.paragraph(" → ".join(s.strip() for s in stages if s)))

        return md.join(*blocks)
