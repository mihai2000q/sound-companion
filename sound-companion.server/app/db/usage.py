"""The cost ledger: one `usage_log` row per model call, the spend sums, and the caps (decisions 37 and 46).

A request opens a `UsageScope` (thread and request id) in a context variable. The code that makes a
model call, wherever it runs in the agent (a tool in a worker thread, the model node), calls `record_usage`
and does not need the ids passed down. Outside a request (scripts, evaluations) there is no scope, so
nothing is written. Recording never raises: a failed write is logged and the request goes on."""
import logging
import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Literal, Protocol

from langchain_core.callbacks import BaseCallbackHandler
from sqlalchemy import Engine, create_engine, func, insert, select

from app.db.models import UsageLog

log = logging.getLogger(__name__)

Purpose = Literal["answer", "rewrite", "rerank", "embed", "eval"]


@dataclass(frozen=True)
class Usage:
    """One model call. `cost` is OpenRouter's `usage.cost`, in credits."""

    purpose: Purpose
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost: float = 0.0


@dataclass(frozen=True)
class Totals:
    calls: int
    prompt_tokens: int
    completion_tokens: int
    cost: float


class UsageStore(Protocol):
    def add(self, thread_id: str, request_id: uuid.UUID, usage: Usage) -> None: ...

    def request_totals(self, request_id: uuid.UUID) -> Totals: ...

    def total_spend(self) -> float: ...

    def thread_rows(self, thread_id: str) -> list[dict]: ...


class SqlUsageStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    @classmethod
    def from_settings(cls) -> "SqlUsageStore":
        from app.config import settings

        return cls(create_engine(settings.database_url_async, pool_pre_ping=True))

    def add(self, thread_id: str, request_id: uuid.UUID, usage: Usage) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                insert(UsageLog).values(
                    thread_id=thread_id, request_id=request_id, purpose=usage.purpose, model=usage.model,
                    prompt_tokens=usage.prompt_tokens, completion_tokens=usage.completion_tokens,
                    cost_credits=usage.cost,
                )
            )

    def request_totals(self, request_id: uuid.UUID) -> Totals:
        query = select(
            func.count(), func.coalesce(func.sum(UsageLog.prompt_tokens), 0),
            func.coalesce(func.sum(UsageLog.completion_tokens), 0), func.coalesce(func.sum(UsageLog.cost_credits), 0),
        ).where(UsageLog.request_id == request_id)
        with self._engine.connect() as conn:
            calls, prompt, completion, cost = conn.execute(query).one()
        return Totals(calls, int(prompt), int(completion), float(cost))

    def total_spend(self) -> float:
        """The database sum is the source of truth for the badge and the caps."""
        with self._engine.connect() as conn:
            return float(conn.execute(select(func.coalesce(func.sum(UsageLog.cost_credits), 0))).scalar_one())

    def thread_rows(self, thread_id: str) -> list[dict]:
        """Every model call of a Conversation, oldest first, for the export (no ids of other tables)."""
        query = (
            select(UsageLog.purpose, UsageLog.model, UsageLog.prompt_tokens, UsageLog.completion_tokens, UsageLog.cost_credits, UsageLog.created_at)
            .where(UsageLog.thread_id == thread_id)
            .order_by(UsageLog.id)
        )
        with self._engine.connect() as conn:
            return [
                {"purpose": r.purpose, "model": r.model, "prompt_tokens": r.prompt_tokens, "completion_tokens": r.completion_tokens,
                 "cost": float(r.cost_credits), "created_at": r.created_at.isoformat()}
                for r in conn.execute(query)
            ]


@dataclass(frozen=True)
class Budget:
    soft: float
    hard: float

    def refuses(self, spend: float) -> bool:
        return spend >= self.hard

    def warns(self, spend: float) -> bool:
        return spend >= self.soft


@dataclass(frozen=True)
class Ledger:
    """What a request needs: where usage is written and read, and the caps."""

    store: UsageStore
    budget: Budget

    @classmethod
    def from_settings(cls) -> "Ledger":
        from app.config import settings

        return cls(SqlUsageStore.from_settings(), Budget(settings.budget_soft_credits, settings.budget_hard_credits))


@dataclass(frozen=True)
class UsageScope:
    store: UsageStore
    thread_id: str
    request_id: uuid.UUID


_scope: ContextVar[UsageScope | None] = ContextVar("usage_scope", default=None)


def open_scope(store: UsageStore, thread_id: str, request_id: uuid.UUID) -> None:
    """Set for the rest of this request. Worker threads started by the agent inherit it."""
    _scope.set(UsageScope(store, thread_id, request_id))


def record_usage(usage: Usage) -> None:
    scope = _scope.get()
    if scope is None:
        return
    try:
        scope.store.add(scope.thread_id, scope.request_id, usage)
    except Exception:
        log.exception("could not write usage_log (%s call, %s credits)", usage.purpose, usage.cost)


def single_name(name: str) -> str:
    """Streamed chunks concatenate string metadata, so a model name arrives doubled ("a/ba/b")."""
    half = len(name) // 2
    return name[:half] if half and name[:half] * 2 == name else name


def usage_of_message(purpose: Purpose, message) -> Usage:
    """The tokens and cost of a finished model call, from its AI message. A model that reports no
    usage (a fake, a provider without `cost`) counts as zero. The cost sits in `response_metadata
    ["token_usage"]`, see `CostChatOpenAI` for the streamed case."""
    metadata = getattr(message, "response_metadata", None) or {}
    tokens = getattr(message, "usage_metadata", None) or {}
    return Usage(
        purpose=purpose,
        model=single_name(str(metadata.get("model_name") or metadata.get("model") or "unknown")),
        prompt_tokens=int(tokens.get("input_tokens") or 0),
        completion_tokens=int(tokens.get("output_tokens") or 0),
        cost=float((metadata.get("token_usage") or {}).get("cost") or 0),
    )


class UsageCallback(BaseCallbackHandler):
    """Records every chat model call it sees as `purpose`. For calls made outside the agent's own
    model node (the rewrite), which has no AI message of its own to read."""

    def __init__(self, purpose: Purpose) -> None:
        self._purpose = purpose

    def on_llm_end(self, response, **kwargs) -> None:
        for generations in response.generations:
            for generation in generations:
                message = getattr(generation, "message", None)
                if message is not None:
                    record_usage(usage_of_message(self._purpose, message))
