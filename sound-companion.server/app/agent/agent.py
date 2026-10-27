from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver

from app.agent.prompt import SYSTEM_PROMPT
from app.rag.retriever import Retriever
from app.rag.rewrite import make_rewriter
from app.tools.registry import build_tools


class CostChatOpenAI(ChatOpenAI):
    """`langchain-openai` drops OpenRouter's `usage.cost` from streamed chunks (decision 46). This keeps the raw
    usage on the chunk, so the aggregated message has it in `response_metadata["token_usage"]["cost"]`, as
    a non-streamed call does. It overrides a private method, so `langchain-openai` is pinned."""

    def _convert_chunk_to_generation_chunk(self, chunk, default_chunk_class, base_generation_info):
        generation = super()._convert_chunk_to_generation_chunk(chunk, default_chunk_class, base_generation_info)
        usage = chunk.get("usage")
        if generation is not None and usage and "cost" in usage:
            generation.message.response_metadata["token_usage"] = usage  # on this chunk only: strings concatenate
        return generation


def make_chat_model(model: str | None = None) -> ChatOpenAI:
    """The chat model from settings, or `model` (an OpenRouter id) when an evaluation compares models."""
    from app.config import settings

    return CostChatOpenAI(
        model=model or settings.openrouter_chat_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        temperature=0,
    )


def build_agent(
    model: BaseChatModel,
    retriever: Retriever,
    checkpointer: BaseCheckpointSaver | None = None,
    rewrite_model: BaseChatModel | None = None,
):
    """The agent: retrieval plus the music tools, no router. Memory only when a checkpointer is given.
    The search tool rewrites queries with `rewrite_model` when one is given."""
    rewriter = make_rewriter(rewrite_model) if rewrite_model else None
    return create_agent(
        model, tools=build_tools(retriever, rewriter), system_prompt=SYSTEM_PROMPT, checkpointer=checkpointer
    )
