from typing import List
from openai import OpenAI
from pathlib import Path
import time

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from .worker import WorkerResult


class AggregatorResult:
    def __init__(self, content: str, pdf_path: Path):
        self.content = content
        self.pdf_path = pdf_path


class Aggregator:
    def __init__(self, client: OpenAI, model: str = "gpt-4.1-mini"):
        self.client = client
        self.model = model

        # Путь к шрифту относительно файла agregator.py
        font_path = Path(__file__).parent / "fonts" / "DejaVuSans.ttf"
        pdfmetrics.registerFont(TTFont("DejaVu", str(font_path)))

    def aggregate(self, results: List[WorkerResult], lang: str = "English") -> AggregatorResult:
        formatted = "\n\n".join([
            f"### {r['type']}\n{r['result']}"
            for r in results
        ])

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": f"You are a professional report writer. Combine these sections in {lang}."
                },
                {
                    "role": "user",
                    "content": formatted
                }
            ],
            temperature=0.7,
            max_tokens=2000,
        )

        final_content = response.choices[0].message.content
        pdf_path = self._save_to_pdf(final_content)
        return AggregatorResult(final_content, pdf_path)

    def _save_to_pdf(self, content: str) -> Path:
        ts = int(time.time())
        pdf_path = Path("./outputs") / f"report_{ts}.pdf"
        pdf_path.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=letter,
            topMargin=0.5 * inch,
            bottomMargin=0.5 * inch,
        )

        styles = getSampleStyleSheet()
        styles["Normal"].fontName = "DejaVu"
        styles["Heading1"].fontName = "DejaVu"

        title_style = ParagraphStyle(
            "Title",
            parent=styles["Heading1"],
            fontName="DejaVu",
            fontSize=22,
            alignment=1,
            spaceAfter=20,
        )

        story = []
        story.append(Paragraph("Research Report", title_style))
        story.append(Spacer(1, 0.3 * inch))

        for line in content.split("\n"):
            if line.strip():
                story.append(Paragraph(line, styles["Normal"]))
            else:
                story.append(Spacer(1, 0.15 * inch))

        doc.build(story)
        print(f"PDF SAVED TO: {pdf_path}")
        return pdf_path
