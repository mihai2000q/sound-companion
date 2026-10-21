import psycopg
import uvicorn
from fastapi import FastAPI, HTTPException

from settings import settings

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/api/health")
async def health():
    try:
        async with await psycopg.AsyncConnection.connect(
            settings.database_url, connect_timeout=3
        ) as conn:
            await conn.execute("SELECT 1")
    except psycopg.Error:
        raise HTTPException(status_code=503, detail={"status": "unavailable", "database": "unreachable"})
    return {"status": "ok", "database": "ok"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}


if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.backend_host, port=settings.backend_port)
