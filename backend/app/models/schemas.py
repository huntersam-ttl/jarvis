"""Schemas for providers, chat, system status, and health."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------- health
class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    environment: str = "dev"


# ---------------------------------------------------------------- providers
class ProviderModel(BaseModel):
    id: str
    owned_by: Optional[str] = None


class ProviderModelList(BaseModel):
    provider: str
    models: List[ProviderModel]
    count: int


class ProviderInfo(BaseModel):
    name: str
    status: str  # connected | offline | not_configured
    base_url: Optional[str] = None
    default_model: Optional[str] = None
    model_count: Optional[int] = None
    api_key_configured: bool = False
    # never include the actual key


class ProviderList(BaseModel):
    providers: List[ProviderInfo]


# ---------------------------------------------------------------- chat
class ChatMessage(BaseModel):
    role: str = "user"
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message to Jarvis")
    model: Optional[str] = Field(
        default=None, description="Optional model override; defaults to config"
    )


class ChatRunMeta(BaseModel):
    requested_model: Optional[str]
    resolved_model: str
    provider: str
    duration_ms: float
    success: bool


class ChatResponse(BaseModel):
    reply: str
    model: str
    provider: str
    status: str  # completed | failed
    run: ChatRunMeta


# ---------------------------------------------------------------- system
class SystemComponent(BaseModel):
    name: str
    status: str  # online | offline | not_installed | not_configured
    detail: Optional[str] = None


class SystemStatus(BaseModel):
    overall: str  # online | degraded | offline
    components: List[SystemComponent]
