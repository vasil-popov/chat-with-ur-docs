from fastapi import APIRouter
from .routes import chat

api_router = APIRouter()
api_router.include_router(chat.router, prefix="/chat")