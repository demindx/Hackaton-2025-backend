from fastapi import FastAPI


app = FastAPI()



@app.get("/pong")
async def test():
    return {"data": "Hello world"}
