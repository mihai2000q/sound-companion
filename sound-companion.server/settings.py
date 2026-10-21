from urllib.parse import quote

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Root .env when run from the server folder; in compose the real environment wins.
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    # Read from the machine's environment, not from .env.
    openrouter_api_key: str
    openrouter_base_url: str

    backend_host: str = "127.0.0.1"
    backend_port: int

    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str
    postgres_port: int

    @property
    def database_url(self) -> str:
        user = quote(self.postgres_user, safe="")
        password = quote(self.postgres_password, safe="")
        return (
            f"postgresql://{user}:{password}@{self.postgres_host}:{self.postgres_port}"
            f"/{self.postgres_db}"
        )


settings = Settings()
