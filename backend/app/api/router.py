from fastapi import APIRouter

from app.api.routes import analyses, judge

api_router = APIRouter()
api_router.include_router(analyses.router)
api_router.include_router(judge.router)
