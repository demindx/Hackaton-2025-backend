from fastapi import FastAPI, Query
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
import os

app = FastAPI()


load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=api_key)
@app.get("/ask")
def ask_gpt(prompt: str = Query(...)):
    print(">>> PROMPT FROM CLIENT:", prompt)

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    answer = completion.choices[0].message.content
    print(">>> GPT ANSWER:", answer)

    return {"answer": answer}
