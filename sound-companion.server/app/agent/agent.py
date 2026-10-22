from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver

from app.agent.prompt import SYSTEM_PROMPT
from app.rag.retriever import Retriever
from app.rag.rewrite import make_rewriter
from app.tools.registry import build_tools


def make_chat_model(model: str | None = None) -> ChatOpenAI:
    """The chat model from settings, or `model` (an OpenRouter id) when an evaluation compares models."""
    from app.config import settings

    return ChatOpenAI(
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
