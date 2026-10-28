"""The judge of the RAGAs evaluation: RAGAs metrics pointed at OpenRouter, and a meter of what the judge spends.

RAGAs is in the optional `ragas` dependency group (`uv sync --group ragas`), so it is imported only here, inside
functions, and the app and its tests never need it."""

import sys
import types
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import httpx

from app.config import settings

MAX_TOKENS = 4096  # RAGAs' default cuts off the statement list of a long answer (IncompleteOutputException)
Scorer = Callable[[dict], Awaitable[float]]  # takes an export entry, returns a score from 0 to 1


@dataclass
class Spend:
    """Judge calls seen so far, per model: [calls, prompt tokens, completion tokens, credits]."""

    models: dict[str, list[float]] = field(default_factory=dict)

    def add(self, body: dict) -> None:
        usage = body.get("usage") or {}
        row = self.models.setdefault(str(body.get("model", "unknown")), [0, 0, 0, 0.0])
        row[0] += 1
        row[1] += int(usage.get("prompt_tokens") or 0)
        row[2] += int(usage.get("completion_tokens") or 0)
        row[3] += float(usage.get("cost") or 0)

    @property
    def credits(self) -> float:
        return sum(row[3] for row in self.models.values())


def metered_client(spend: Spend, transport: httpx.AsyncBaseTransport | None = None):
    """An OpenRouter client that adds the `usage` of every response to `spend`. RAGAs hides the raw responses, so
    the meter sits in the HTTP layer, where `usage.cost` is (decision 46)."""
    from openai import AsyncOpenAI

    async def meter(response: httpx.Response) -> None:
        await response.aread()
        if response.status_code != 200:  # an error body (a 429) spent nothing
            return
        try:
            spend.add(response.json())
        except ValueError:  # not JSON, an error page: nothing to count
            pass

    http = httpx.AsyncClient(event_hooks={"response": [meter]}, transport=transport, timeout=120)
    # the free upstream pool of some models answers 429 now and then, so retry longer than the default 2
    return AsyncOpenAI(
        api_key=settings.openrouter_api_key, base_url=settings.openrouter_base_url, http_client=http, max_retries=6
    )


def import_ragas():
    """RAGAs 0.4.3 imports `langchain_community.chat_models.vertexai`, which langchain-community 0.4 no longer has.
    A stand-in module lets the import through. The judge never uses Vertex."""
    name = "langchain_community.chat_models.vertexai"
    if name not in sys.modules:
        try:
            __import__(name)
        except ImportError:
            module = types.ModuleType(name)
            module.ChatVertexAI = type("ChatVertexAI", (), {})
            sys.modules[name] = module
    from ragas.llms.base import llm_factory
    from ragas.embeddings.base import embedding_factory
    from ragas.metrics import collections

    return llm_factory, embedding_factory, collections


def make_scorers(client, judge_model: str, embedding_model: str, contexts_of: Callable[[dict, str], list[str]]) -> dict[str, Scorer]:
    """The four metrics as scorers of one export entry. `contexts_of(entry, metric)` says what counts as its contexts for that metric."""
    llm_factory, embedding_factory, metrics = import_ragas()
    llm = llm_factory(judge_model, client=client, temperature=0, max_tokens=MAX_TOKENS)
    embeddings = embedding_factory("openai", model=embedding_model, client=client)
    faithfulness = metrics.Faithfulness(llm=llm)
    relevancy = metrics.AnswerRelevancy(llm=llm, embeddings=embeddings)
    precision = metrics.ContextPrecision(llm=llm)
    recall = metrics.ContextRecall(llm=llm)

    async def run(metric, **kwargs) -> float:
        return float((await metric.ascore(**kwargs)).value)

    return {
        "faithfulness": lambda e: run(faithfulness, user_input=e["question"], response=e["answer"], retrieved_contexts=contexts_of(e, "faithfulness")),
        "answer_relevancy": lambda e: run(relevancy, user_input=e["question"], response=e["answer"]),
        "context_precision": lambda e: run(precision, user_input=e["question"], reference=e["reference"], retrieved_contexts=contexts_of(e, "context_precision")),
        "context_recall": lambda e: run(recall, user_input=e["question"], reference=e["reference"], retrieved_contexts=contexts_of(e, "context_recall")),
    }
