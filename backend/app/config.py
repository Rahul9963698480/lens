from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = _BACKEND_DIR / ".env"
load_dotenv(_ENV_FILE, override=True)


def normalize_postgres_url(url: str) -> str:
    """Strip driver-specific dialect suffixes so asyncpg accepts the DSN."""
    for prefix in ("postgresql+asyncpg://", "postgresql+psycopg://", "postgres+asyncpg://"):
        if url.startswith(prefix):
            return "postgresql://" + url.split("://", 1)[1]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "XYMP Lens Backend"
    SUPABASE_DB_URL: str
    OPENAI_API_KEY: str = ""
    MODEL_ID: str = "gpt-4o"

    @property
    def asyncpg_dsn(self) -> str:
        return normalize_postgres_url(self.SUPABASE_DB_URL)


settings = Settings()
