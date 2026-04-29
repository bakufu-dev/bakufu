"""Room アグリゲート、エンティティ、VO のファクトリ群.

``docs/features/room/test-design.md`` 準拠。empire / workflow / agent と
同パターン: 各ファクトリは本番コンストラクタ経由で *妥当* なデフォルト
インスタンスを返し、キーワード上書きを許可し、結果を
:class:`WeakValueDictionary` に登録する。これにより :func:`is_synthetic` が
後から、frozen Pydantic モデルを変更せずにテスト由来オブジェクトを
フラグ付けできる。

デフォルト Room は ``LeaderMembership`` 1 件と空の PromptKit prefix を
組み合わせる ── 最短構築経路で追加セットアップなしに TC-UT-RM-001 を
カバーするため。空 members リストが要るテストは ``members=[]`` を
明示的に渡せる (Aggregate レベル不変条件は 0〜:data:`MAX_MEMBERS` を
受理する ── leader 必須はアプリケーション層責務。TC-UT-RM-029 参照)。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4
from weakref import WeakValueDictionary

from bakufu.domain.room import (
    AgentMembership,
    PromptKit,
    Room,
)
from bakufu.domain.value_objects import Role
from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Sequence

# モジュールスコープのレジストリ。値は弱参照で GC 圧は中立に保つ。
_SYNTHETIC_REGISTRY: WeakValueDictionary[int, BaseModel] = WeakValueDictionary()


def is_synthetic(instance: BaseModel) -> bool:
    """``instance`` が本モジュールのファクトリで生成されたものなら ``True`` を返す。"""
    cached = _SYNTHETIC_REGISTRY.get(id(instance))
    return cached is instance


def _register(instance: BaseModel) -> None:
    """``instance`` を合成レジストリに記録する。"""
    _SYNTHETIC_REGISTRY[id(instance)] = instance


# ---------------------------------------------------------------------------
# AgentMembership
# ---------------------------------------------------------------------------
def make_agent_membership(
    *,
    agent_id: UUID | None = None,
    role: Role = Role.DEVELOPER,
    joined_at: datetime | None = None,
) -> AgentMembership:
    """妥当な :class:`AgentMembership` を構築する (デフォルト role は DEVELOPER)。"""
    membership = AgentMembership(
        agent_id=agent_id if agent_id is not None else uuid4(),
        role=role,
        joined_at=joined_at if joined_at is not None else datetime.now(UTC),
    )
    _register(membership)
    return membership


def make_leader_membership(
    *,
    agent_id: UUID | None = None,
    joined_at: datetime | None = None,
) -> AgentMembership:
    """populated Room シナリオ用の LEADER role :class:`AgentMembership` を構築する。"""
    return make_agent_membership(
        agent_id=agent_id,
        role=Role.LEADER,
        joined_at=joined_at,
    )


# ---------------------------------------------------------------------------
# PromptKit
# ---------------------------------------------------------------------------
def make_prompt_kit(
    *,
    prefix_markdown: str = "",
) -> PromptKit:
    """妥当な :class:`PromptKit` を構築する (デフォルト prefix_markdown は空)。"""
    kit = PromptKit(prefix_markdown=prefix_markdown)
    _register(kit)
    return kit


def make_long_prompt_kit() -> PromptKit:
    """上限境界 (10000 文字) の :class:`PromptKit` を構築する。"""
    return make_prompt_kit(prefix_markdown="a" * 10_000)


# ---------------------------------------------------------------------------
# Room
# ---------------------------------------------------------------------------
def make_room(
    *,
    room_id: UUID | None = None,
    name: str = "Vモデル開発室",
    description: str = "",
    workflow_id: UUID | None = None,
    members: Sequence[AgentMembership] | None = None,
    prompt_kit: PromptKit | None = None,
    archived: bool = False,
) -> Room:
    """妥当な :class:`Room` を構築する。

    上書きなしの場合、最小妥当な Room を返す: members ゼロ件、description 空、
    デフォルトの空 PromptKit、``archived=False``。populated members が要る
    テストは ``members=[...]`` で明示的に渡すこと。
    """
    if prompt_kit is None:
        prompt_kit = make_prompt_kit()
    room = Room(
        id=room_id if room_id is not None else uuid4(),
        name=name,
        description=description,
        workflow_id=workflow_id if workflow_id is not None else uuid4(),
        members=list(members) if members is not None else [],
        prompt_kit=prompt_kit,
        archived=archived,
    )
    _register(room)
    return room


def make_archived_room(**overrides: object) -> Room:
    """冪等性 / terminal-violation セットアップ用に ``archived=True`` の Room を構築する。"""
    return make_room(archived=True, **overrides)  # pyright: ignore[reportArgumentType]


def make_populated_room(
    *,
    room_id: UUID | None = None,
    leader_agent_id: UUID | None = None,
    developer_agent_id: UUID | None = None,
    workflow_id: UUID | None = None,
) -> Room:
    """LEADER 1 名 + DEVELOPER 1 名の membership を持つ Room を構築する。

    非空 member リスト上で add / remove / update / archive 遷移を検証する
    TC-IT-RM-001 / 002 ラウンドトリップシナリオ向け。

    ``workflow_id`` は :func:`make_room` に転送される ── インフラ結合テストが
    seeded な workflow FK ターゲットを渡せるように。
    """
    return make_room(
        room_id=room_id,
        workflow_id=workflow_id,
        members=[
            make_leader_membership(agent_id=leader_agent_id),
            make_agent_membership(agent_id=developer_agent_id, role=Role.DEVELOPER),
        ],
    )


def make_room_with_secret_prompt_kit(
    *,
    room_id: UUID | None = None,
    prefix_markdown: str,
    workflow_id: UUID | None = None,
) -> Room:
    """secret を含む ``prefix_markdown`` を持つ PromptKit を備えた Room を構築する。

    ``MaskedText`` が行を SQLite に書く前に埋め込み secret を redact することを
    検証するインフラテストで使用する (§確定 R1-J 不可逆性凍結)。

    呼び出し側は、masking ゲートウェイの正規表現パターンに一致するトークンを
    含む ``prefix_markdown`` を渡す責務を持つ ── ラウンドトリップが
    non-identity (raw → masked) となるように。
    """
    kit = make_prompt_kit(prefix_markdown=prefix_markdown)
    return make_room(
        room_id=room_id,
        workflow_id=workflow_id,
        prompt_kit=kit,
    )


__all__ = [
    "is_synthetic",
    "make_agent_membership",
    "make_archived_room",
    "make_leader_membership",
    "make_long_prompt_kit",
    "make_populated_room",
    "make_prompt_kit",
    "make_room",
    "make_room_with_secret_prompt_kit",
]
