"""③ 학습평가 — 인쇄 교재용 정식 평가, 10~15문항 + 해설. MD + XLSX 출력."""
from __future__ import annotations

import os

from core import llm, prompt_loader, chunker
from exporters import md_writer as md
from exporters import xlsx_assessment
from studio._base import StudioBase, StudioContext, StudioResult


class ChapterAssessmentStudio(StudioBase):
    key = "chapter_assessment"
    label = "학습평가"
    icon = "✅"
    order = 3

    def run(self, ctx: StudioContext) -> StudioResult:
        min_count = int(os.getenv("TSB_ASSESSMENT_MIN", "10"))
        max_count = int(os.getenv("TSB_ASSESSMENT_MAX", "15"))

        body = chunker.fit_to_budget(ctx.body_text, budget_chars=80000)
        system, user = prompt_loader.render(
            "chapter_assessment_ko",
            body=body,
            min_count=min_count,
            max_count=max_count,
        )
        data = llm.call_json(system, user, model=ctx.model)
        questions = data.get("questions") or []

        md_body = self._render_md(questions)
        md_path = self.write_md(ctx, "chapter_assessment.md", md_body)
        xlsx_path = xlsx_assessment.write(questions, ctx.output_dir / "chapter_assessment.xlsx")

        return StudioResult(
            studio=self.key,
            primary_path=md_path,
            artifacts=[xlsx_path],
            summary=f"학습평가 생성 완료 — {len(questions)}문항",
        )

    def _render_md(self, questions: list[dict]) -> str:
        blocks: list[str] = [md.h1("학습평가")]

        for q in questions:
            no = q.get("no")
            qtext = (q.get("question") or "").strip()
            qtype = (q.get("type") or "mcq").lower()
            blocks.append(md.h2(f"{no:02d}. {qtext}" if isinstance(no, int) else f"{no}. {qtext}"))

            if qtype == "mcq":
                choices = q.get("choices") or []
                marks = ["①", "②", "③", "④"]
                lines = []
                for i, c in enumerate(choices[:4]):
                    mark = marks[i] if i < 4 else f"({i + 1})"
                    lines.append(f"{mark} {str(c).strip()}")
                blocks.append("\n".join(lines) + "\n")
            elif qtype == "ox":
                blocks.append("다음 지문이 올바르면 ○, 올바르지 않으면 ✕를 작성하시오. (    )\n")
            elif qtype == "short":
                blocks.append("(    )에 알맞은 답을 작성하시오.\n")

        # 정답 및 해설
        blocks.append("\n---\n")
        blocks.append(md.h2("정답 및 해설"))
        for q in questions:
            no = q.get("no")
            ans = q.get("answer", "")
            explanation = (q.get("explanation") or "").strip()
            diff = q.get("difficulty", "")
            src = q.get("source_page", "")
            head = f"**{no:02d}. {ans}**" if isinstance(no, int) else f"**{no}. {ans}**"
            meta_bits = [b for b in [f"난이도 {diff}" if diff else "", src] if b]
            meta = f"  _({' · '.join(meta_bits)})_" if meta_bits else ""
            blocks.append(f"{head}{meta}\n\n{explanation}\n")

        return md.join(*blocks)
