from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver

from app.agent.prompt import SYSTEM_PROMPT
from app.rag.retriever import Retriever
from app.tools.registry import build_tools


def make_chat_model() -> ChatOpenAI:
    from app.config import settings

    return ChatOpenAI(
        model=settings.openrouter_chat_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        temperature=0,
    )


def build_agent(model: BaseChatModel, retriever: Retriever, checkpointer: BaseCheckpointSaver | None = None):
    """The agent: retrieval plus the music tools, no router. Memory only when a checkpointer is given."""
    return create_agent(
        model, tools=build_tools(retriever), system_prompt=SYSTEM_PROMPT, checkpointer=checkpointer
    )
