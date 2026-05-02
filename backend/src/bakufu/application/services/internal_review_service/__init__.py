"""InternalReviewService パッケージ — INTERNAL_REVIEW Gate CRUD と downstream 連携。

設計書: docs/features/internal-review-gate/application/basic-design.md §モジュール契約
"""

from __future__ import annotations

from bakufu.application.services.internal_review_service._gate_manager import (
    InternalReviewService,
)

__all__ = ["InternalReviewService"]
