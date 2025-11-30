from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse
from openai import OpenAI
import asyncio
import uuid

from .config import config
from .task_queue import task_queue
from .superviser import Supervisor
from .worker import Worker
from .agregator import Aggregator


app = FastAPI()
client = OpenAI(api_key=config.openai_api_key)


@app.on_event("startup")
async def startup_event():
    # Запускаем 3 параллельных воркера для HTTP-очереди
    for _ in range(3):
        asyncio.create_task(task_queue.worker())


# -------------------------------
#    WebSocket версия с task_id
# -------------------------------
@app.websocket("/ws")
async def ws_agent(ws: WebSocket):
    await ws.accept()

    try:
        # Получаем сообщение
        prompt = await ws.receive_text()

        # Генерируем task_id
        task_id = str(uuid.uuid4())

        await ws.send_json({
            "task_id": task_id,
            "event": "received",
            "message": "Prompt received"
        })

        # Supervisor
        supervisor = Supervisor(client)
        plan = supervisor.plan(prompt)
        supervisor.save_plan(plan)

        total_steps = len(plan["subtasks"])

        await ws.send_json({
            "task_id": task_id,
            "event": "supervisor_start",
            "plan": plan,
            "total_steps": total_steps,
            "progress": 5
        })

        # Worker
        worker = Worker(client)
        worker_results = []

        for i, sub in enumerate(plan["subtasks"], start=1):
            await ws.send_json({
                "task_id": task_id,
                "event": "subtask_start",
                "step": i,
                "total_steps": total_steps,
                "prompt": sub["prompt"],
                "progress": int(5 + (i / total_steps) * 80)
            })

            result = await worker.process_subtask_async(sub)
            worker_results.append(result)

            await ws.send_json({
                "task_id": task_id,
                "event": "subtask_done",
                "step": i,
                "result_type": result["type"],
                "progress": int(5 + (i / total_steps) * 80)
            })

        worker.save_results_to_json(worker_results)

        await ws.send_json({
            "task_id": task_id,
            "event": "worker_done",
            "message": "All subtasks completed",
            "progress": 90
        })

        # Aggregator
        aggregator = Aggregator(client)
        final = aggregator.aggregate(worker_results, lang=plan["final_lang"])

        await ws.send_json({
            "task_id": task_id,
            "event": "aggregator_done",
            "pdf_path": str(final.pdf_path),
            "progress": 100
        })

        await ws.send_json({
            "task_id": task_id,
            "event": "finished",
            "message": "Task completed"
        })

        await ws.close()

    except Exception as e:
        await ws.send_json({
            "event": "error",
            "message": str(e)
        })
        await ws.close()


# -----------------------------------
#      HTTP API для очереди задач
# -----------------------------------

@app.post("/submit")
async def submit(prompt: str):
    async def pipeline():
        supervisor = Supervisor(client)
        plan = supervisor.plan(prompt)
        supervisor.save_plan(plan)

        worker = Worker(client)
        worker_results = await worker.run_all_async(plan["subtasks"])
        worker.save_results_to_json(worker_results)

        aggregator = Aggregator(client)
        final = aggregator.aggregate(worker_results, lang=plan["final_lang"])

        return {"pdf_path": str(final.pdf_path)}

    task_id = await task_queue.add_task(pipeline())
    return {"task_id": task_id}


@app.get("/status/{task_id}")
async def status(task_id: str):
    return {"status": task_queue.status.get(task_id, "NOT_FOUND")}


@app.get("/result/{task_id}")
async def result(task_id: str):
    if task_queue.status.get(task_id) != "DONE":
        return {"error": "Task not finished"}
    return task_queue.results[task_id]


@app.get("/download/{task_id}")
async def download(task_id: str):
    result = task_queue.results.get(task_id)
    if not result:
        return {"error": "Task not found"}

    return FileResponse(result["pdf_path"])
