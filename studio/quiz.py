"""④ 퀴즈 — 보조 학습용, 15~20문항. MD + XLSX 출력."""
from __future__ import annotations

import os

from core import llm, prompt_loader, chunker
from exporters import md_writer as md
from exporters import xlsx_quiz
from studio._base import StudioBase, StudioContext, StudioResult


class QuizStudio(StudioBase):
    key = "quiz"
    label = "퀴즈 (보조)"
    icon = "❓"
    order = 4

    def run(self, ctx: StudioContext) -> StudioResult:
        min_count = int(os.getenv("TSB_QUIZ_MIN", "15"))
        max_count = int(os.getenv("TSB_QUIZ_MAX", "20"))

        body = chunker.fit_to_budget(ctx.body_text, budget_chars=80000)
        system, user = prompt_loader.render(
            "quiz_ko",
            body=body,
            min_count=min_count,
            max_count=max_count,
        )
        data = llm.call_json(system, user, model=ctx.model)
        questions = data.get("questions") or []

        md_body = self._render_md(questions)
        md_path = self.write_md(ctx, "quiz.md", md_body)
        xlsx_path = xlsx_quiz.write(questions, ctx.output_dir / "quiz.xlsx")

        return StudioResult(
            studio=self.key,
            primary_path=md_path,
            artifacts=[xlsx_path],
            summary=f"퀴즈 생성 완료 — {len(questions)}문항",
        )

    def _render_md(self, questions: list[dict]) -> str:
        blocks: list[str] = [md.h1("퀴즈 (보조 학습용)")]

        for q in questions:
            no = q.get("no")
            qtext = (q.get("question") or "").strip()
            qtype = (q.get("type") or "mcq").lower()
            cat = (q.get("category") or "").strip()

            head = f"{no:02d}. {qtext}" if isinstance(no, int) else f"{no}. {qtext}"
            if cat:
                head = f"{head} _[{cat}]_"
            blocks.append(md.h3(head))

            if qtype == "mcq":
                choices = q.get("choices") or []
                marks = ["①", "②", "③", "④"]
                lines = [f"{marks[i] if i < 4 else f'({i + 1})'} {str(c).strip()}"
                         for i, c in enumerate(choices[:4])]
                blocks.append("\n".join(lines) + "\n")
            elif qtype == "ox":
                blocks.append("(  O  /  X  )\n")
            elif qtype == "short":
                blocks.append("답: (                          )\n")

        blocks.append("\n---\n")
        blocks.append(md.h2("정답 및 해설"))
        for q in questions:
            no = q.get("no")
            ans = q.get("answer", "")
            explanation = (q.get("explanation") or "").strip()
            head = f"**{no:02d}. {ans}**" if isinstance(no, int) else f"**{no}. {ans}**"
            blocks.append(f"{head} — {explanation}\n")

        return md.join(*blocks)
