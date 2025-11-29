from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from openai import OpenAI
from .config import config
from .superviser import Supervisor
from .worker import Worker
from .agregator import Aggregator
import os
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI()
client = OpenAI(api_key=config.openai_api_key)

origins = [
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/ask")
async def ask_agent(prompt: str = Query(...)):
    supervisor = Supervisor(client=client, model="gpt-4.1")
    plan = supervisor.plan(prompt)

    worker = Worker(client=client, model="gpt-4.1")
    worker_results = worker.run_all(plan.subtasks)

    aggregator = Aggregator(client=client, model="gpt-4.1")
    final = aggregator.aggregate(worker_results)

    return FileResponse(
        path=final.pdf_path,
        media_type="application/pdf",
        filename="report.pdf",
    )
