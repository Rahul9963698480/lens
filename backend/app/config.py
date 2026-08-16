from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


def normalize_postgres_url(url: str) -> str:
    """Strip driver-specific dialect suffixes so asyncpg accepts the DSN."""
    for prefix in ("postgresql+asyncpg://", "postgresql+psycopg://", "postgres+asyncpg://"):
        if url.startswith(prefix):
            return "postgresql://" + url.split("://", 1)[1]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "XYMP Lens Backend"
    SUPABASE_DB_URL: str
    OPENAI_API_KEY: str = ""
    MODEL_ID: str = "gpt-4o"

    @property
    def asyncpg_dsn(self) -> str:
        return normalize_postgres_url(self.SUPABASE_DB_URL)


settings = Settings()
