import pytest
from pydantic import ValidationError

from app.config import Settings
from app.rag import factory
from app.rag.hybrid import HybridRetriever
from app.rag.retriever import VectorRetriever


@pytest.fixture(autouse=True)
def fake_retrievers(monkeypatch):
    """No network and no database: `from_settings` returns a marker instead of a real retriever."""
    monkeypatch.setattr(VectorRetriever, "from_settings", classmethod(lambda cls: "vector retriever"))
    monkeypatch.setattr(HybridRetriever, "from_settings", classmethod(lambda cls: "hybrid retriever"))


def test_the_configured_mode_picks_the_retriever(monkeypatch):
    monkeypatch.setattr(factory.settings, "retriever_mode", "hybrid")
    assert factory.make_retriever() == "hybrid retriever"
    monkeypatch.setattr(factory.settings, "retriever_mode", "vector")
    assert factory.make_retriever() == "vector retriever"


def test_an_explicit_mode_beats_the_config(monkeypatch):
    monkeypatch.setattr(factory.settings, "retriever_mode", "vector")
    assert factory.make_retriever("hybrid") == "hybrid retriever"


def test_an_unknown_mode_is_refused():
    with pytest.raises(ValueError, match="vector.*hybrid"):
        factory.make_retriever("keyword")


def test_the_default_mode_is_vector_and_an_unknown_value_fails_at_startup(monkeypatch):
    assert Settings.model_fields["retriever_mode"].default == "vector"
    monkeypatch.setenv("RETRIEVER_MODE", "keyword")  # the environment beats the .env file
    with pytest.raises(ValidationError, match="retriever_mode"):
        Settings()
