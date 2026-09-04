"""Jarvis backend configuration.

Settings are loaded from environment variables / .env via pydantic-settings.
Secrets (OMNIROUTE_API_KEY) are never printed or logged.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- OmniRoute ----
    omniroute_base_url: str = Field(
        default="http://127.0.0.1:20128/v1",
        alias="OMNIROUTE_BASE_URL",
    )
    omniroute_api_key: str = Field(default="", alias="OMNIROUTE_API_KEY")
    omniroute_default_model: str = Field(default="auto/glm", alias="OMNIROUTE_DEFAULT_MODEL")

    # ---- Backend ----
    jarvis_env: str = Field(default="dev", alias="JARVIS_ENV")
    jarvis_backend_host: str = Field(default="127.0.0.1", alias="JARVIS_BACKEND_HOST")
    jarvis_backend_port: int = Field(default=8000, alias="JARVIS_BACKEND_PORT")
    jarvis_cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="JARVIS_CORS_ORIGINS",
    )

    @field_validator("omniroute_api_key")
    @classmethod
    def _strip_key(cls, v: str) -> str:
        return (v or "").strip()

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.jarvis_cors_origins.split(",") if o.strip()]

    @property
    def omniroute_configured(self) -> bool:
        return bool(self.omniroute_api_key)

    @property
    def is_dev(self) -> bool:
        return self.jarvis_env.lower() == "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()
