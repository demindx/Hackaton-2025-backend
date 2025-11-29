from typing import List, TypedDict
from openai import OpenAI
import json
from pathlib import Path
import time


class WorkerSubTask(TypedDict):
    type: str
    prompt: str


class Supervisor:
    def __init__(self, client: OpenAI, model: str = "gpt-4.1-mini"):
        self.client = client
        self.model = model

    def plan(self, prompt: str) -> dict:
        """Разбивает промпт на подзадачи и выбирает язык"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": """You are a task planner. 
                    1. Determine the language of the user's request.
                    2. Break the task into 3–5 subtasks.
                    3. Return JSON: {"language": "...", "subtasks": [{"type": "...", "prompt": "..."}]}"""
                },
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        data = json.loads(response.choices[0].message.content)

        return {
            "subtasks": [
                {"type": sub.get("type", "research"), "prompt": sub.get("prompt", "")}
                for sub in data.get("subtasks", [])
            ],
            "final_lang": data.get("language", "English")
        }

    def save_plan(self, plan: dict) -> Path:
        ts = int(time.time())
        path = Path("./outputs") / f"plan_{ts}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)
        print(f"PLAN SAVED TO: {path}")
        return path
