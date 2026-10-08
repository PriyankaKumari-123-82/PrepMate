from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./prepmate.db"
    jwt_secret: str = "development-only-secret"
    jwt_expire_minutes: int = 60 * 24
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    embed_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536
    upload_dir: Path = Path("./uploads")
    cors_origins: str = "http://localhost:5173"
    max_upload_mb: int = 30
    max_pdf_pages: int = 250


@lru_cache
def get_settings() -> Settings:
    return Settings()

