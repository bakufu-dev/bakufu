"""``room_members`` テーブル — Room Aggregate 用 AgentMembership 子行。

各 :class:`bakufu.domain.room.value_objects.AgentMembership` を DB 行として保存
する。1 つの Room は複数のメンバを持ち得、各エントリは ``(room_id, agent_id, role)``
の 3 つ組で識別される。

設計コントラクト（§確定 R1-D）:

* ``room_id`` FK → ``rooms.id`` ON DELETE CASCADE: Room を削除すると全メンバーシップ
  行を消去する。
* ``agent_id`` は ``agents.id`` への FK を **持たない**。Room §確定 は Agent 存在
  チェックをアプリケーション層の責務として凍結する（``RoomService.add_member`` が
  ``AgentRepository.find_by_id`` を呼ぶ）。FK CASCADE は Agent 行が消えたときに
  メンバーシップをサイレントに削除してしまう。FK RESTRICT はアーカイブ済み Agent
  を Room からきれいに削除することをブロックしてしまう。MVP モデルではどちらも
  正しくない — アプリケーション層チェックのみとする。
* 複合 PK ``(room_id, agent_id, role)`` に加え、CI Layer 2 アーキテクチャ テストの
  検出性のために明示的な名前付き ``UniqueConstraint`` を併設する。PK は UNIQUE を
  暗黙に含むが、アーキ テストの ``__table_args__`` スキャンは明示的な制約宣言のみ
  を捕捉する（agent_providers パターン、detailed-design §確定 R1-D の根拠）。
* ``joined_at`` は ``DateTime(timezone=True)`` を使うため、aiosqlite は読み取り時に
  UTC ``tzinfo`` を保持する — 水和された ``AgentMembership.joined_at`` は
  room/detailed-design で凍結された通り常に tz-aware。
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import Base, UUIDStr


class RoomMemberRow(Base):
    """``room_members`` テーブルの ORM マッピング。"""

    __tablename__ = "room_members"

    room_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("rooms.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    agent_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        primary_key=True,
        nullable=False,
        # agents.id への FK は意図的に持たない — モジュール docstring 参照。
    )
    role: Mapped[str] = mapped_column(String(32), primary_key=True, nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        # §確定 R1-D: 明示的な UniqueConstraint が複合 PK をミラーすることで、
        # CI Layer 2 アーキ テストが ``__table_args__`` をスキャンして UNIQUE 制約の
        # 存在をアサートできる。PK 由来の暗黙 UNIQUE はそのスキャンには見えないため、
        # この冗長性が多層防御の基盤として機能する。
        UniqueConstraint(
            "room_id",
            "agent_id",
            "role",
            name="uq_room_members_triplet",
        ),
    )


__all__ = ["RoomMemberRow"]
