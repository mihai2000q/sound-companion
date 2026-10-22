import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.agent import build_agent, make_chat_model
from app.agent.memory import open_checkpointer
from app.api import chat, health
from app.config import settings
from app.db.migrate import run_migrations
from app.rag.retriever import VectorRetriever


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(run_migrations)
    async with open_checkpointer() as saver:
        app.state.agent = build_agent(make_chat_model(), VectorRetriever.from_settings(), saver)
        yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.client_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(health.router)
app.include_router(chat.router)


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.backend_host, port=settings.backend_port)
