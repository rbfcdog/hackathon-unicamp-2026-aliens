from fastapi import APIRouter

from app.api.routes import analyses, chat, judge, processes

api_router = APIRouter()
api_router.include_router(analyses.router)
api_router.include_router(chat.router)
api_router.include_router(processes.router)
api_router.include_router(judge.router)
