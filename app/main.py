from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from openai import OpenAI

from .config import config
from .superviser import Supervisor
from .worker import Worker
from .agregator import Aggregator

app = FastAPI()
client = OpenAI(api_key=config.openai_api_key)


@app.get("/ask", response_class=FileResponse)
async def ask_agent(prompt: str = Query(...)):
    supervisor = Supervisor(client=client, model="gpt-4.1-mini")
    plan = supervisor.plan(prompt)
    supervisor.save_plan(plan)

    worker = Worker(client=client)
    worker_results = await worker.run_all_async(plan["subtasks"])
    worker.save_results_to_json(worker_results)

    aggregator = Aggregator(client=client, model="gpt-4.1-mini")
    final = aggregator.aggregate(worker_results, lang=plan["final_lang"])

    return FileResponse(
        path=final.pdf_path,
        media_type="application/pdf",
        filename=f"report_{plan['final_lang']}.pdf",
    )


@app.websocket("/ws")
async def ws_agent(ws: WebSocket):
    await ws.accept()
    try:
        prompt = await ws.receive_text()
        await ws.send_text(f"supervisor: получил запрос — '{prompt[:80]}...'")

        supervisor = Supervisor(client=client, model="gpt-4.1-mini")
        plan = supervisor.plan(prompt)
        supervisor.save_plan(plan)

        await ws.send_text(f"supervisor: язык '{plan['final_lang']}'")
        await ws.send_text(f"supervisor: {len(plan['subtasks'])} шаг(ов)")

        worker = Worker(client=client)
        worker_results = []

        for i, sub in enumerate(plan["subtasks"], start=1):
            await ws.send_text(f"worker: шаг {i} — {sub['type']}")
            res = await worker.process_subtask_async(sub)
            worker_results.append(res)

        worker.save_results_to_json(worker_results)
        await ws.send_text("worker: все шаги готовы")

        aggregator = Aggregator(client=client, model="gpt-4.1-mini")
        final = aggregator.aggregate(worker_results, lang=plan["final_lang"])

        await ws.send_text(f"done: PDF готов → {final.pdf_path}")
        await ws.close()

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await ws.send_text(f"error: {str(e)}")
        await ws.close()
