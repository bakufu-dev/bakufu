"""GET /health エンドポイント。"""

from __future__ import annotations

from fastapi import APIRouter

from bakufu.interfaces.http.schemas.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """bakufu 稼働確認エンドポイント。"""
    return HealthResponse(status="ok")
