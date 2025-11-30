import json
import time
from pathlib import Path
from typing import TypedDict
from openai import OpenAI


class WorkerSubTask(TypedDict):
    type: str
    prompt: str


class Supervisor:
    def __init__(self, client: OpenAI, model: str = "gpt-4.1-mini"):
        self.client = client
        self.model = model

    # Определение языка через OpenAI
    def detect_language(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": """
                        Detect the language of the user's message.
                        Return ONLY the language name in English.
                    """
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        return response.choices[0].message.content.strip()

    # Генерация subtasks
    def plan(self, prompt: str) -> dict:
        final_lang = self.detect_language(prompt)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": """
                        Break the user's request into 3–5 research subtasks.
                        Output as JSON: {"subtasks":[{"type":"...","prompt":"..."}]}
                    """
                },
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )

        data = json.loads(response.choices[0].message.content)

        return {
            "subtasks": data.get("subtasks", []),
            "final_lang": final_lang
        }

    def save_plan(self, plan: dict) -> Path:
        ts = int(time.time())
        path = Path("./outputs") / f"plan_{ts}.json"
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)

        print(f"PLAN SAVED TO: {path}")
        return path
