"""EmpireService — Empire Aggregate 操作の application 層サービス。"""

from __future__ import annotations

from bakufu.application.ports.empire_repository import EmpireRepository


class EmpireService:
    """Empire Aggregate 操作の thin CRUD サービス骨格 (確定 F)。"""

    def __init__(self, repo: EmpireRepository) -> None:
        self._repo = repo
