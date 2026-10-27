from app.config import RETRIEVER_MODES, settings
from app.rag.hybrid import HybridRetriever
from app.rag.retriever import Retriever, VectorRetriever


def make_retriever(mode: str | None = None) -> Retriever:
    """The retriever for `mode` (`vector` or `hybrid`), the configured one when it is None."""
    mode = mode or settings.retriever_mode
    if mode == "vector":
        return VectorRetriever.from_settings()
    if mode == "hybrid":
        return HybridRetriever.from_settings()
    raise ValueError(f"retriever mode must be one of {RETRIEVER_MODES}, got {mode!r}")
