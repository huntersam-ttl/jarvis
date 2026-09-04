"""Jarvis backend configuration.

Settings are loaded from environment variables / .env via pydantic-settings.
Secrets (OPENROUTER_API_KEY) are never printed or logged.
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

    # ---- OpenRouter ----
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        alias="OPENROUTER_BASE_URL",
    )
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_default_model: str = Field(
        default="openai/gpt-4o-mini", alias="OPENROUTER_DEFAULT_MODEL"
    )

    # ---- Trading Agent (Phase 2 bridge) ----
    trading_agent_base_url: str = Field(default="", alias="TRADING_AGENT_BASE_URL")
    trading_agent_api_key: str = Field(default="", alias="TRADING_AGENT_API_KEY")
    trading_default_mode: str = Field(default="paper", alias="TRADING_DEFAULT_MODE")

    # ---- Backend ----
    jarvis_env: str = Field(default="dev", alias="JARVIS_ENV")
    jarvis_backend_host: str = Field(default="127.0.0.1", alias="JARVIS_BACKEND_HOST")
    jarvis_backend_port: int = Field(default=8000, alias="JARVIS_BACKEND_PORT")
    jarvis_cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="JARVIS_CORS_ORIGINS",
    )
    # Coding agent project registry (comma-separated absolute paths).
    jarvis_allowed_projects: str = Field(default="", alias="JARVIS_ALLOWED_PROJECTS")

    @field_validator("openrouter_api_key")
    @classmethod
    def _strip_key(cls, v: str) -> str:
        return (v or "").strip()

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.jarvis_cors_origins.split(",") if o.strip()]

    @property
    def openrouter_configured(self) -> bool:
        return bool(self.openrouter_api_key)

    @property
    def is_dev(self) -> bool:
        return self.jarvis_env.lower() == "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()
