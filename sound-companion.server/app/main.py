import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.agent.agent import build_agent, make_chat_model
from app.agent.memory import open_checkpointer
from app.limits import RateLimiter
from app.api import chat, health, monitoring, threads
from app.config import settings
from app.db.logs import SqlLogWriter
from app.db.migrate import run_migrations
from app.db.threads import SqlThreadStore
from app.db.usage import Ledger
from app.rag.factory import make_retriever


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(run_migrations)
    app.state.ledger = Ledger.from_settings()
    app.state.log_writer = SqlLogWriter.from_settings()
    app.state.thread_store = SqlThreadStore.from_settings()
    app.state.rate_limiter = RateLimiter()
    async with open_checkpointer() as saver:
        app.state.agent = build_agent(make_chat_model(), make_retriever(), saver, make_chat_model(settings.openrouter_rewrite_model))
        yield


app = FastAPI(lifespan=lifespan)
app.add_exception_handler(RequestValidationError, chat.invalid_request)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.client_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(health.router)
app.include_router(chat.router)
app.include_router(monitoring.router)
app.include_router(threads.router)


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.backend_host, port=settings.backend_port)
