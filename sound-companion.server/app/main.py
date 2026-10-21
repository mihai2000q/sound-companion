import uvicorn
from fastapi import FastAPI

from app.api import health
from app.config import settings

app = FastAPI()
app.include_router(health.router)


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.backend_host, port=settings.backend_port)
