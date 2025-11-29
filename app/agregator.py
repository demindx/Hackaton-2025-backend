from dataclasses import dataclass
from pathlib import Path
from typing import List

from fastapi import WebSocket
from openai import OpenAI
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from .worker import WorkerResult


@dataclass
class AggregationResult:
    final_text: str
    pdf_path: Path


class Aggregator:
    def __init__(self, client: OpenAI, model: str = "gpt-4.1-mini") -> None:
        self.client = client
        self.model = model

    def _build_aggregator_prompt(self, results: List[WorkerResult]) -> str:
        import json
        return f"""
Тебе даётся список промежуточных результатов разных типов воркеров.
Нужно:
- убрать повторы и мусор,
- собрать один краткий, структурированный отчёт,
- выделить ключевые выводы, цифры, описания графиков/таблиц.

Входные данные (JSON):
{json.dumps(results, ensure_ascii=False, indent=2)}

Выведи чистый текст отчёта с заголовками и списками. Без лишних комментариев.
""".strip()

    # ----- Обычный режим -----
    def aggregate(self, results: List[WorkerResult]) -> AggregationResult:
        prompt = self._build_aggregator_prompt(results)
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "Ты редактор отчётов. Делаешь текст чистым и структурированным."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=2000,
        )
        final_text = completion.choices[0].message.content.strip()
        pdf_path = self._save_pdf(final_text)
        return AggregationResult(final_text=final_text, pdf_path=pdf_path)

    # ----- Режим с WebSocket-логами -----
    async def aggregate_ws(
        self, results: List[WorkerResult], ws: WebSocket
    ) -> AggregationResult:
        await ws.send_text("aggregator: комбинирую всю информацию…")
        prompt = self._build_aggregator_prompt(results)
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "Ты редактор отчётов. Делаешь текст чистым и структурированным."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=2000,
        )
        final_text = completion.choices[0].message.content.strip()
        await ws.send_text("aggregator: текст собран, конвертирую в PDF…")
        pdf_path = self._save_pdf(final_text)
        return AggregationResult(final_text=final_text, pdf_path=pdf_path)

    def _save_pdf(self, text: str) -> Path:
        output_dir = Path("./outputs")
        output_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = output_dir / "report.pdf"

        # юникод-шрифт
        pdfmetrics.registerFont(
            TTFont("DejaVu", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
        )

        c = canvas.Canvas(str(pdf_path), pagesize=A4)
        c.setFont("DejaVu", 10)
        width, height = A4
        x, y = 50, height - 50

        for line in text.splitlines():
            if not line:
                y -= 14
            else:
                c.drawString(x, y, line[:150])
                y -= 14
            if y < 50:
                c.showPage()
                c.setFont("DejaVu", 10)
                y = height - 50

        c.save()
        return pdf_path
