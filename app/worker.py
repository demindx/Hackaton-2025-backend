import asyncio
from typing import TypedDict, List
from pathlib import Path
import json
import time

from openai import OpenAI
import requests

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
            results = [
                f"- {item.get('title')}: {item.get('snippet')}"
                for item in data.get("organic", [])[:5]
            ]
            return "\n".join(results) if results else "No results found"
        except Exception as e:
            return f"Search error: {str(e)}"

    def _process_with_openai(self, topic: str, search_results: str) -> str:
        response = self.client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a research analyst. Based on search results, write a structured report."
                },
                {
                    "role": "user",
                    "content": f"""Topic: {topic}

Search Results:
{search_results}

Write:
1. Key findings
2. Insights
3. Sources
4. Conclusion"""
                }
            ],
            temperature=0.7,
            max_tokens=1500
        )
        return response.choices[0].message.content

    def _run_research(self, topic: str) -> str:
        search_results = self._search_web(topic)
        return self._process_with_openai(topic, search_results)

    async def process_subtask_async(self, subtask: dict) -> WorkerResult:
        loop = asyncio.get_running_loop()
        text_result = await loop.run_in_executor(
            None, self._run_research, subtask["prompt"]
        )
        return WorkerResult(
            type=subtask["type"],
            prompt=subtask["prompt"],
            result=text_result,
        )

    async def run_all_async(self, subtasks: List[dict]) -> List[WorkerResult]:
        tasks = [self.process_subtask_async(sub) for sub in subtasks]
        return await asyncio.gather(*tasks)

    def save_results_to_json(self, results, path: Path | None = None) -> Path:
        if path is None:
            ts = int(time.time())
            path = Path("./outputs") / f"worker_results_{ts}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"WORKER RESULTS SAVED TO: {path}")
        return path
