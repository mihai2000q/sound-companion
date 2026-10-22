"""The tools the agent binds: knowledge-base search plus the music tools."""
from langchain_core.tools import BaseTool

from app.rag.retriever import Retriever
from app.tools.chords import make_chord_info_tool
from app.tools.intervals import make_interval_between_tool, make_scale_info_tool
from app.tools.search import make_search_tool


def build_tools(retriever: Retriever) -> list[BaseTool]:
    return [make_search_tool(retriever), make_chord_info_tool(), make_scale_info_tool(), make_interval_between_tool()]
