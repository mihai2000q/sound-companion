import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health
from app.config import settings
from app.db.migrate import run_migrations


@asynccontextmanager
async def lifespan(_: FastAPI):
    await asyncio.to_thread(run_migrations)
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.client_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(health.router)


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.backend_host, port=settings.backend_port)
