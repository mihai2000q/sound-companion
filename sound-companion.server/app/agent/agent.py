from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver

from app.agent.prompt import SYSTEM_PROMPT
from app.rag.retriever import Retriever
from app.tools.search import make_search_tool


def make_chat_model() -> ChatOpenAI:
    from app.config import settings

    return ChatOpenAI(
        model=settings.openrouter_chat_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        temperature=0,
    )


def build_agent(model: BaseChatModel, retriever: Retriever, checkpointer: BaseCheckpointSaver | None = None):
    """The agent: one retrieval tool, no router. Memory only when a checkpointer is given."""
    return create_agent(
        model, tools=[make_search_tool(retriever)], system_prompt=SYSTEM_PROMPT, checkpointer=checkpointer
    )
