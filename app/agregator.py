from typing import List
from pathlib import Path
import time

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from openai import OpenAI
from .worker import WorkerResult


class AggregatorResult:
    def __init__(self, content: str, pdf_path: Path):
        self.content = content
        self.pdf_path = pdf_path


class Aggregator:
    def __init__(self, client: OpenAI, model="gpt-4.1-mini"):
        self.client = client
        self.model = model

        font_path = Path(__file__).parent / "fonts" / "DejaVuSans.ttf"
        pdfmetrics.registerFont(TTFont("DejaVu", str(font_path)))

    def aggregate(self, results: List[WorkerResult], lang: str) -> AggregatorResult:
        formatted = "\n\n".join([f"### {r['type']}\n{r['result']}" for r in results])

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": f"Write a final report in {lang}."},
                {"role": "user", "content": formatted}
            ]
        )

        content = response.choices[0].message.content
        pdf_path = self._save_to_pdf(content)
        return AggregatorResult(content=content, pdf_path=pdf_path)

    def _save_to_pdf(self, content: str) -> Path:
        ts = int(time.time())
        pdf_path = Path("./outputs") / f"report_{ts}.pdf"
        pdf_path.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(str(pdf_path), pagesize=letter)

        styles = getSampleStyleSheet()
        styles["Normal"].fontName = "DejaVu"

        story = [Paragraph("Research Report", styles["Heading1"]), Spacer(1, 0.2 * inch)]

        for line in content.split("\n"):
            if line.strip():
                story.append(Paragraph(line, styles["Normal"]))
            else:
                story.append(Spacer(1, 0.1 * inch))

        doc.build(story)
        return pdf_path
