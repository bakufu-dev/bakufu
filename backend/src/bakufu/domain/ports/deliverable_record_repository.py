"""AbstractDeliverableRecordRepository — DeliverableRecord 永続化 Port 定義。

domain 層の Port インターフェース。infrastructure 層の具体実装に依存しない。

設計書: docs/features/deliverable-template/ai-validation/basic-design.md REQ-AIVM-003
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bakufu.domain.deliverable_record.deliverable_record import DeliverableRecord
    from bakufu.domain.value_objects.identifiers import DeliverableId, DeliverableRecordId


class AbstractDeliverableRecordRepository(ABC):
    """DeliverableRecord の永続化インターフェース（domain port）。

    7 段階 save() パターンで冪等な upsert を提供する（§確定 D）。
    """

    @abstractmethod
    async def save(self, record: DeliverableRecord) -> None:
        """DeliverableRecord を永続化する（冪等、7 段階 save() パターン）。"""
        ...

    @abstractmethod
    async def find_by_id(self, record_id: DeliverableRecordId) -> DeliverableRecord | None:
        """record_id で DeliverableRecord を 1 件取得する。"""
        ...

    @abstractmethod
    async def find_by_deliverable_id(
        self, deliverable_id: DeliverableId
    ) -> DeliverableRecord | None:
        """deliverable_id で最新の DeliverableRecord を 1 件取得する。"""
        ...


__all__ = ["AbstractDeliverableRecordRepository"]
