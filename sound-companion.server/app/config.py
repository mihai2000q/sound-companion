from urllib.parse import quote

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Root .env when run from the backend folder; in compose the real environment wins.
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    # Read from the machine's environment, not from .env.
    openrouter_api_key: str
    openrouter_base_url: str
    openrouter_chat_model: str = "openai/gpt-4o-mini"
    openrouter_embedding_model: str = "openai/text-embedding-3-small"

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
        """Plain psycopg style, for the migration runner and scripts."""
        return self._database_url("postgresql")

    @property
    def database_url_async(self) -> str:
        """SQLAlchemy psycopg style, for the vector store (PGEngine)."""
        return self._database_url("postgresql+psycopg")


settings = Settings()
