from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from openai import OpenAI

from .config import config
from .superviser import Supervisor
from .worker import Worker
from .agregator import Aggregator

app = FastAPI()

client = OpenAI(api_key=config.openai_api_key)

# ----- HTTP: вернуть готовый PDF -----
@app.get("/ask", response_class=FileResponse)
async def ask_agent(prompt: str = Query(...)):
    supervisor = Supervisor(client=client, model="gpt-4.1")
    plan = supervisor.plan(prompt)
    supervisor.save_plan(plan)

    worker = Worker(client=client, model="gpt-4.1-mini")
    worker_results = worker.run_all(plan.subtasks)
    worker.save_results_to_json(worker_results)

    aggregator = Aggregator(client=client, model="gpt-4.1-mini")
    final = aggregator.aggregate(worker_results)

    return FileResponse(
        path=final.pdf_path,
        media_type="application/pdf",
        filename="report.pdf",
    )

# ----- WebSocket: фазы работы -----
@app.websocket("/ws")
async def ws_agent(ws: WebSocket):
    await ws.accept()
    try:
        # 1. получаем запрос пользователя как первую строку
        prompt = await ws.receive_text()
        await ws.send_text(f"supervisor: получил запрос — '{prompt[:80]}...'")

        supervisor = Supervisor(client=client, model="gpt-4.1")
        await ws.send_text("supervisor: формирую план задач…")
        plan = supervisor.plan(prompt)
        supervisor.save_plan(plan)
        await ws.send_text(f"supervisor: создано {len(plan.subtasks)} шаг(ов)")

        worker = Worker(client=client, model="gpt-4.1-mini")
        worker_results = []
        for i, sub in enumerate(plan.subtasks, start=1):
            await ws.send_text(
                f"worker: старт шага {i} (type={sub['type']})"
            )
            res = await worker.process_subtask_ws(sub, ws)
            worker_results.append(res)
            await ws.send_text(
                f"worker: завершён шаг {i} (type={sub['type']})"
            )

        worker.save_results_to_json(worker_results)
        await ws.send_text("worker: все шаги выполнены, результаты сохранены в JSON")

        aggregator = Aggregator(client=client, model="gpt-4.1-mini")
        final = await aggregator.aggregate_ws(worker_results, ws)

        await ws.send_text(f"done: готовый PDF по пути {final.pdf_path}")

        await ws.close()

    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        await ws.send_text(f"error: {e}")
        await ws.close()
