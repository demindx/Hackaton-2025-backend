from fastapi import FastAPI
from .config import config




app = FastAPI()



@app.get("/pong")
async def test():
    return {"data": "Hello world"}
