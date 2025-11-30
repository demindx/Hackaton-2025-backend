import asyncio
from typing import TypedDict, List
from pathlib import Path
import json
import time
import requests

from openai import OpenAI
from .config import config


class WorkerResult(TypedDict):
    type: str
    prompt: str
    result: str


class Worker:
    def __init__(self, client: OpenAI):
        self.client = client
        self.serper_api_key = config.serper_api_key

    def _search_web(self, query: str) -> str:
        url = "https://google.serper.dev/search"
        payload = {"q": query, "num": 10}
        headers = {
            "X-API-KEY": self.serper_api_key,
            "Content-Type": "application/json"
        }

        try:
            r = requests.post(url, json=payload, headers=headers, timeout=10)
            r.raise_for_status()
            data = r.json()

            items = data.get("organic", [])[:5]
            return "\n".join(
                f"- {i.get('title')}: {i.get('snippet')}" for i in items
            ) or "No results"
        except Exception as e:
            return f"Search error: {e}"

    def _process_with_openai(self, topic: str, search_results: str) -> str:
        response = self.client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "Analyse search results."},
                {
                    "role": "user",
                    "content": f"Topic: {topic}\n\nSearch:\n{search_results}"
                }
            ],
            temperature=0.7
        )
        return response.choices[0].message.content

    def _run_research(self, topic: str) -> str:
        search_data = self._search_web(topic)
        return self._process_with_openai(topic, search_data)

    async def process_subtask_async(self, sub) -> WorkerResult:
        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(None, self._run_research, sub["prompt"])
        return WorkerResult(type=sub["type"], prompt=sub["prompt"], result=text)

    async def run_all_async(self, subtasks: List[dict]):
        tasks = [self.process_subtask_async(s) for s in subtasks]
        return await asyncio.gather(*tasks)

    def save_results_to_json(self, results):
        ts = int(time.time())
        path = Path("./outputs") / f"worker_results_{ts}.json"
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"WORKER RESULTS SAVED TO: {path}")
        return path
