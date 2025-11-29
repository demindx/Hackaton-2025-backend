from dataclasses import dataclass
from typing import TypedDict, List
from pathlib import Path
import json
import time

from openai import OpenAI


class WorkerSubTask(TypedDict):
    type: str      # метка виртуального "воркера"
    prompt: str    # ПОЛНЫЙ промпт для LLM


@dataclass
class SupervisionResult:
    raw_query: str
    subtasks: list[WorkerSubTask]


class Supervisor:
    def __init__(self, client: OpenAI, model: str = "gpt-4.1") -> None:
        self.client = client
        self.model = model

    def plan(self, raw_query: str) -> SupervisionResult:
        system = (
            "Ты планировщик. По запросу пользователя составляешь ПЛАН РАБОТЫ "
            "для одного универсального воркера.\n"
            "Каждый шаг = виртуальный воркер: type + prompt.\n"
            "Отвечай ТОЛЬКО JSON-массивом."
        )

        user = f"""
Запрос пользователя:
\"\"\"{raw_query}\"\"\"

Разбей этот запрос на несколько логических шагов.
Для каждого шага создай объект:

{{
  "type": "строка-метка, например 'research', 'stats_analyzer', 'plot_designer', 'image_extractor', 'table_extractor' и т.п.",
  "prompt": "ПОЛНЫЙ текстовый промпт для LLM. Внутри промпта объясни воркеру:
             - кто он (роль),
             - что именно нужно сделать на этом шаге,
             - как искать/обрабатывать данные (текст, таблицы, изображения, графики),
             - в каком формате вернуть результат (текст, JSON, описание таблиц/графиков/изображений)."
}}

Требования:
- Все инструкции для 'воркера' должны быть ВНУТРИ поля 'prompt'.
- Поле 'type' — только метка для агрегации, воркер НЕ должен на него опираться.
- Форматы вывода делай как можно более структурированными (JSON там, где возможно).

Верни ТОЛЬКО JSON-массив таких объектов, без текста до или после.
""".strip()

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
        )

        content = resp.choices[0].message.content
        try:
            subtasks: List[WorkerSubTask] = json.loads(content)
        except json.JSONDecodeError:
            subtasks = [{
                "type": "generic",
                "prompt": (
                    "Ты универсальный воркер. Выполни весь этот запрос целиком, "
                    "найди и проанализируй все нужные данные, верни структурированный текстовый отчёт:\n"
                    + raw_query
                ),
            }]

        return SupervisionResult(raw_query=raw_query, subtasks=subtasks)

    def save_plan(self, plan: SupervisionResult, path: Path | None = None) -> Path:
        if path is None:
            ts = int(time.time())
            path = Path("./outputs") / f"plan_{ts}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(
                {"raw_query": plan.raw_query, "subtasks": plan.subtasks},
                f,
                ensure_ascii=False,
                indent=2,
            )
        print("PLAN SAVED TO:", path)
        return path
