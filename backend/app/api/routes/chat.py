from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.api.schemas.chat import ChatRequest
from app.db.database import get_session
from app.deps.dependency_container import di_container_instance
from app.services import chat_service

router = APIRouter()


@router.post("/stream", summary="Chat API (SSE streaming)")
async def chat_stream(req: ChatRequest, db: Session = Depends(get_session)):
    agent = di_container_instance.get_agent(req.arch)
    return StreamingResponse(
        chat_service.stream_chat(agent, req.message, req.file_ids or [], db),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("", summary="Chat API")
async def chat(
    req: ChatRequest,
    db: Session = Depends(get_session),
):
    agent = di_container_instance.get_agent(req.arch)
    return await chat_service.invoke_chat(agent, req.message, req.file_ids or [], db)
