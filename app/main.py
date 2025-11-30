from typing import Optional

from fastapi import (
    FastAPI,
    Query,
    WebSocket,
    WebSocketDisconnect,
    HTTPException,
    Depends,
    status,
)
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from openai import OpenAI
from sqlalchemy.orm import Session
from jose import jwt, JWTError
import os

from .config import config
from .superviser import Supervisor
from .worker import Worker
from .agregator import Aggregator

from .database import engine, get_db
from .models import Base, User, RequestHistory
from .security import hash_password, verify_password, create_access_token, SECRET_KEY, ALGORITHM
from .deps import get_current_user, get_optional_user


app = FastAPI()
Base.metadata.create_all(bind=engine)

client = OpenAI(api_key=config.openai_api_key)

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared data for current prompt and PDF path
current_prompt: Optional[str] = None
current_pdf_path: Optional[str] = None


# ---------- AUTH ----------

@app.post("/auth/register")
def register(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    existing = db.query(User).filter(User.email == form.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    user = User(email=form.username, hashed_password=hash_password(form.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "email": user.email}


@app.post("/auth/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    token = create_access_token({"sub": user.id})
    return {"access_token": token, "token_type": "bearer"}


# ---------- HISTORY (HTTP) ----------

@app.get("/history")
def get_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(RequestHistory)
        .filter(RequestHistory.user_id == current_user.id)
        .order_by(RequestHistory.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": r.id,
            "prompt": r.prompt,
            "pdf_path": r.pdf_path,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


# ---------- SUBMIT (HTTP, без истории для гостя) ----------

@app.get("/submit")
async def submit(
    prompt: str = Query(...),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
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

    # Save request history only for authenticated users
    if current_user is not None:
        record = RequestHistory(
            user_id=current_user.id,
            prompt=prompt,
            pdf_path=current_pdf_path,
        )
        db.add(record)
        db.commit()

    return JSONResponse(content={"message": "Processing started"})


# ---------- WEBSOCKET LOGS + HISTORY ----------

@app.websocket("/ws")
async def ws_agent(
    ws: WebSocket,
    db: Session = Depends(get_db),
):
    await ws.accept()
    try:
        prompt = await ws.receive_text()
        await ws.send_text(f"supervisor: received request — '{prompt[:80]}...'")

        supervisor = Supervisor(client=client, model="gpt-4.1-mini")
        plan = supervisor.plan(prompt)
        supervisor.save_plan(plan)

        await ws.send_text(f"supervisor: output language '{plan['final_lang']}'")
        await ws.send_text(f"supervisor: {len(plan['subtasks'])} step(s)")

        worker = Worker(client=client)
        worker_results = []

        for i, sub in enumerate(plan["subtasks"], start=1):
            await ws.send_text(f"worker: step {i} — {sub['type']}")
            res = await worker.process_subtask_async(sub)
            worker_results.append(res)

        worker.save_results_to_json(worker_results)
        await ws.send_text("worker: all steps completed")

        aggregator = Aggregator(client=client, model="gpt-4.1-mini")
        final = aggregator.aggregate(worker_results, lang=plan["final_lang"])

        global current_pdf_path
        current_pdf_path = final.pdf_path

        # Try to get JWT from query string: /ws?token=...
        user: Optional[User] = None
        token = ws.query_params.get("token")
        if token:
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                user_id = payload.get("sub")
                if user_id is not None:
                    user = db.query(User).filter(User.id == user_id).first()
            except JWTError:
                user = None

        # Save history only if user is authenticated
        if user is not None and current_pdf_path:
            record = RequestHistory(
                user_id=user.id,
                prompt=prompt,
                pdf_path=current_pdf_path,
            )
            db.add(record)
            db.commit()

        await ws.send_text(f"done: PDF ready → {final.pdf_path}")
        await ws.close()

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await ws.send_text(f"error: {str(e)}")
        await ws.close()


# ---------- PDF DOWNLOAD ----------

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
