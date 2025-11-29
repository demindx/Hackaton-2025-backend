from dataclasses import dataclass
from typing import TypedDict, List
from openai import OpenAI
import json


class WorkerSubTask(TypedDict):
    type: str       # имя "виртуального воркера"
    prompt: str     # полный промпт для этого воркера


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
            "Ты планировщик. Твоя задача — по запросу пользователя "
            "составить ПЛАН РАБОТЫ для одного универсального воркера.\n"
            "Воркеров как кодовых сущностей не существует — есть только типы задач и промпты.\n"
            "Каждый элемент плана — это виртуальный 'воркер': type + prompt."
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
             - как искать/обрабатывать данные,
             - в каком формате вернуть результат (текст, JSON, описание таблиц/графиков/изображений)."
}}

Требования:
- Все инструкции для 'воркера' должны быть ВНУТРИ поля 'prompt'.
- Поле 'type' — только метка для агрегации, воркер НЕ должен на него опираться.
- Форматы вывода (особенно для таблиц, графиков, диаграмм) делай как можно более структурированными (JSON).

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
            # fallback: один универсальный шаг, если модель накосячила с JSON
            subtasks = [{
                "type": "generic",
                "prompt": (
                    "Ты универсальный воркер. Выполни весь этот запрос целиком, "
                    "найди и проанализируй все нужные данные, верни структурированный текстовый отчёт:\n"
                    + raw_query
                ),
            }]

        return SupervisionResult(raw_query=raw_query, subtasks=subtasks)
