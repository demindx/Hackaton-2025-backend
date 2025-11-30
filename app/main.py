from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from .config import config
from .superviser import Supervisor
from .worker import Worker
from .agregator import Aggregator
import asyncio
import os


app = FastAPI()
client = OpenAI(api_key=config.openai_api_key)


origins = [
    "http://localhost:5173",  # frontend origin
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Shared data for current prompt and PDF path
current_prompt = None
current_pdf_path = None


@app.get("/submit")
async def submit(prompt: str = Query(...)):
    global current_prompt, current_pdf_path
    current_prompt = prompt


    supervisor = Supervisor(client=client, model="gpt-4.1-mini")
    plan = supervisor.plan(prompt)
    supervisor.save_plan(plan)


    worker = Worker(client=client)
    worker_results = await worker.run_all_async(plan["subtasks"])
    worker.save_results_to_json(worker_results)


    aggregator = Aggregator(client=client, model="gpt-4.1-mini")
    final = aggregator.aggregate(worker_results, lang=plan["final_lang"])


    current_pdf_path = final.pdf_path


    return JSONResponse(content={"message": "Processing started"})


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


        global current_pdf_path
        current_pdf_path = final.pdf_path


        await ws.send_text(f"done: PDF готов → {final.pdf_path}")
        await ws.close()


    except WebSocketDisconnect:
        pass
    except Exception as e:
        await ws.send_text(f"error: {str(e)}")
        await ws.close()


@app.get("/get_pdf")
async def get_pdf():
    global current_pdf_path
    print("Serving PDF from:", current_pdf_path)
    if current_pdf_path and os.path.isfile(current_pdf_path):
        return FileResponse(
            current_pdf_path,
            media_type="application/pdf",
            filename=os.path.basename(current_pdf_path),
        )
    else:
        print("PDF file not found:", current_pdf_path)
        raise HTTPException(status_code=404, detail="PDF not found")
