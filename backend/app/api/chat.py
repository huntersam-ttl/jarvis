"""Chat endpoint — the Jarvis command interface."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.exceptions import ChatError
from app.deps import get_chat_service
from app.models.schemas import ChatRequest, ChatResponse
from app.services.chat import ChatService

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    try:
        return await chat_service.handle(request.message, model=request.model)
    except ChatError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
