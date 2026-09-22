from functools import lru_cache
from typing import List

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Wiki Agentic RAG Platform"
    app_env: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    secret_key: str
    access_token_expire_minutes: int = 60
    algorithm: str = "HS256"

    database_url: str

    cors_origins: List[AnyHttpUrl] = Field(default_factory=list)

    dify_api_base_url: AnyHttpUrl = "https://api.dify.ai"
    dify_api_key: str
    dify_default_dataset_id: str
    dify_chat_app_id: str

    max_upload_size_mb: int = 50

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
