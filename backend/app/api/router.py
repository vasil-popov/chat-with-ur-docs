from fastapi import APIRouter
from .routes import chat, expenses, exercises

api_router = APIRouter()
api_router.include_router(chat.router, prefix="/chat")
api_router.include_router(expenses.router, prefix="/expenses", tags=["expenses"])
api_router.include_router(exercises.router, prefix="/exercises", tags=["exercises"])