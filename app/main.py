from fastapi import FastAPI, Query
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
from .config import config
import os

app = FastAPI()


client = OpenAI(api_key=config.openai_api_key)
@app.get("/ask")
def ask_gpt(prompt: str = Query(...)):
    print(">>> PROMPT FROM CLIENT:", prompt)

    completion = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    answer = completion.choices[0].message.content
    print(">>> GPT ANSWER:", answer)

    return {"answer": answer}
