"""ExternalReviewGateService — ExternalReviewGate Aggregate 操作の application 層サービス。"""

from __future__ import annotations

from bakufu.application.ports.external_review_gate_repository import (
    ExternalReviewGateRepository,
)


class ExternalReviewGateService:
    """ExternalReviewGate Aggregate 操作の thin CRUD サービス骨格 (確定 F)。"""

    def __init__(self, repo: ExternalReviewGateRepository) -> None:
        self._repo = repo
