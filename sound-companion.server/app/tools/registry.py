"""The tools the agent binds: knowledge-base search plus the music tools."""
from langchain_core.tools import BaseTool

from app.config import settings
from app.rag.retriever import Retriever
from app.rag.rewrite import Rewriter
from app.tools.chords import make_chord_info_tool
from app.tools.frequency import make_note_frequency_tool
from app.tools.intervals import make_interval_between_tool, make_scale_info_tool
from app.tools.search import make_search_tool
from app.tools.transpose import make_transpose_tool


def build_tools(retriever: Retriever, rewriter: Rewriter | None = None) -> list[BaseTool]:
    return [make_search_tool(retriever, k=settings.search_k, rewriter=rewriter), make_chord_info_tool(), make_scale_info_tool(), make_interval_between_tool(), make_note_frequency_tool(), make_transpose_tool()]
