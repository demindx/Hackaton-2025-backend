from typing import TypedDict, List
from pathlib import Path
import json
import time

from fastapi import WebSocket
from openai import OpenAI

from .superviser import WorkerSubTask


class WorkerResult(TypedDict):
    type: str
    prompt: str
    result: str


class Worker:
    def __init__(self, client: OpenAI, model: str = "gpt-4.1-mini") -> None:
        self.client = client
        self.model = model

    # ----- Синхронный режим (HTTP) -----
    def process_subtask(self, subtask: WorkerSubTask) -> WorkerResult:
        user_prompt = subtask["prompt"]

        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты универсальный исполнитель. Выполняй задачу РОВНО так, как описано в пользовательском промпте. "
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
        results: List[WorkerResult] = []
        for sub in subtasks:
            results.append(self.process_subtask(sub))
        return results

    def save_results_to_json(
        self, results: List[WorkerResult], path: Path | None = None
    ) -> Path:
        if path is None:
            ts = int(time.time())
            path = Path("./outputs") / f"worker_results_{ts}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print("WORKER RESULTS SAVED TO:", path)
        return path

    # ----- Режим с WebSocket-логами -----
    async def process_subtask_ws(
        self, subtask: WorkerSubTask, ws: WebSocket
    ) -> WorkerResult:
        await ws.send_text(
            f"worker: начинаю задачу type={subtask['type']}"
        )

        user_prompt = subtask["prompt"]

        # тут остаётся синхронный вызов клиента OpenAI, но обёрнут в async функцию
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты универсальный исполнитель. Выполняй задачу РОВНО так, как описано в пользовательском промпте. "
                        "Строго соблюдай формат."
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=1500,
        )
        result_text = completion.choices[0].message.content.strip()

        await ws.send_text(
            f"worker: получил ответ для type={subtask['type']}"
        )

        return WorkerResult(
            type=subtask["type"],
            prompt=subtask["prompt"],
            result=result_text,
        )
