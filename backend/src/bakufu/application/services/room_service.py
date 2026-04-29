"""RoomService — Room Aggregate 操作の application 層サービス。"""

from __future__ import annotations

from bakufu.application.ports.room_repository import RoomRepository


class RoomService:
    """Room Aggregate 操作の thin CRUD サービス骨格 (確定 F)。"""

    def __init__(self, repo: RoomRepository) -> None:
        self._repo = repo
