from typing import Literal, get_args
from urllib.parse import quote

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

RetrieverMode = Literal["vector", "hybrid"]
RETRIEVER_MODES = get_args(RetrieverMode)


class Settings(BaseSettings):
    # Root .env when run from the backend folder; in compose the real environment wins.
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    # Read from the machine's environment, not from .env.
    openrouter_api_key: str
    openrouter_base_url: str
    openrouter_chat_model: str = "openai/gpt-4o-mini"
    openrouter_rewrite_model: str = "openai/gpt-4o-mini"  # cheap model for multi-query rewrite
    openrouter_judge_model: str = "google/gemini-2.5-flash-lite"  # scores answers in the RAGAs evaluation (eval/run_ragas.py)
    openrouter_embedding_model: str = "openai/text-embedding-3-small"

    # Which Retriever the chat route and the retrieval metrics use (decision log, Story 15).
    retriever_mode: RetrieverMode = "vector"

    # Chunks one `search_knowledge_base` call returns (merged over the rewrites). Fewer chunks lift context precision.
    search_k: int = Field(default=5, ge=1, le=10)
    # Candidates fetched per query before the cut and the rerank trim them to `search_k` (used only when one is on).
    search_pool: int = Field(default=10, ge=1, le=30)
    # Drop candidates scoring under this share of the best score (0 = off).
    search_score_ratio: float = Field(default=0.85, ge=0, le=1)
    # A cheap model (the rewrite model) keeps only the chunks that help answer the question.
    search_rerank: bool = True

    # Budget caps in OpenRouter credits, treated as USD (decision 37). Soft warns, hard refuses.
    budget_soft_credits: float = 1.0
    budget_hard_credits: float = 4.0

    backend_host: str = "127.0.0.1"
    backend_port: int
    client_port: int

    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str
    postgres_port: int

    @property
    def client_origins(self) -> list[str]:
        return [f"http://localhost:{self.client_port}", f"http://127.0.0.1:{self.client_port}"]

    def _database_url(self, scheme: str) -> str:
        user = quote(self.postgres_user, safe="")
        password = quote(self.postgres_password, safe="")
        return (
            f"{scheme}://{user}:{password}@{self.postgres_host}:{self.postgres_port}"
            f"/{self.postgres_db}"
        )

    @property
    def database_url(self) -> str:
        """Plain psycopg style, for the health check and the checkpointer pool."""
        return self._database_url("postgresql")

    @property
    def database_url_async(self) -> str:
        """SQLAlchemy psycopg style, for our ORM models, Alembic and the vector store (PGEngine)."""
        return self._database_url("postgresql+psycopg")


settings = Settings()
