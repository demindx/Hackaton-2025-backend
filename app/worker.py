from typing import TypedDict, List
from openai import OpenAI
from .superviser import WorkerSubTask
import json
from pathlib import Path


class WorkerResult(TypedDict):
    type: str
    prompt: str       # исходный промпт (по желанию)
    result: str       # ответ LLM (может быть JSON-строкой)


class Worker:
    def __init__(self, client: OpenAI, model: str = "gpt-4.1-mini") -> None:
        self.client = client
        self.model = model

    def process_subtask(self, subtask: WorkerSubTask) -> WorkerResult:
        """
        Универсальный воркер: он вообще не знает про типы.
        Получает ПОЛНЫЙ промпт и просто его исполняет.
        """
        user_prompt = subtask["prompt"]

        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты универсальный исполнитель. Выполняй задачу РОВНО так, как описано в пользовательском промпте.\n"
                        "Строго соблюдай требуемый формат ответа (текст, JSON, описание графика/таблицы и т.п.)."
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=1500,
        )
        result_text = completion.choices[0].message.content.strip()

        return WorkerResult(
            type=subtask["type"],
            prompt=subtask["prompt"],
            result=result_text,
        )

    def run_all(self, subtasks: List[WorkerSubTask]) -> List[WorkerResult]:
        """
        Бежим по всем подзадачам по очереди.
        После каждой — ничего не держим в памяти, новый вызов = новая "голова".
        """
        results: List[WorkerResult] = []
        for sub in subtasks:
            results.append(self.process_subtask(sub))
        return results

    def save_results_to_json(self, results: List[WorkerResult], path: Path | None = None) -> Path:
        """
        Записать результаты в JSON-файл, чтобы потом aggregator.py их забрал.
        """
        if path is None:
            path = Path("./outputs/worker_results.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        return path
