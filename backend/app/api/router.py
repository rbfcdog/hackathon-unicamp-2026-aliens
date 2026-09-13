from fastapi import APIRouter

from app.api.routes import analyses, bank, chat, judge, processes

api_router = APIRouter()
api_router.include_router(analyses.router)
api_router.include_router(bank.router)
api_router.include_router(chat.router)
api_router.include_router(processes.router)
api_router.include_router(judge.router)
