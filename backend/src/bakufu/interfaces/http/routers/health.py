"""GET /health エンドポイント。"""

from __future__ import annotations

from fastapi import APIRouter

from bakufu.interfaces.http.schemas.common import HealthResponse

router = APIRouter()


class HealthHttpRoutes:
    """Health HTTP 入口をクラスメソッドに閉じる。"""

    @classmethod
    async def health(cls) -> HealthResponse:
        """bakufu 稼働確認エンドポイント。"""
        return HealthResponse(status="ok")


router.add_api_route(
    "/health",
    HealthHttpRoutes.health,
    methods=["GET"],
    response_model=HealthResponse,
)
