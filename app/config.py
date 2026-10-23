from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(value: str) -> str:
    """Escape raw @ characters in URL credentials without double-encoding them."""
    if "://" not in value:
        return value

    parts = urlsplit(value)
    if "@" not in parts.netloc:
        return value

    credentials, separator, address = parts.netloc.rpartition("@")
    if not separator or "@" not in credentials:
        return value

    netloc = f"{credentials.replace('@', '%40')}@{address}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


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
    storage_backend: Literal["local", "supabase"] = "local"
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_storage_bucket: str = "prepmate-pdfs"
    cors_origins: str = "http://localhost:5173"
    max_upload_mb: int = 30
    max_pdf_pages: int = 250


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.database_url = normalize_database_url(settings.database_url)
    return settings
