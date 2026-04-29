"""Empire アグリゲートと参照 VO のファクトリ群.

``docs/features/empire/test-design.md`` (REQ-EM-001〜005, factories) 準拠。
各ファクトリは:

* 本番コンストラクタ経由で *妥当* なデフォルトインスタンスを返す。
* キーワード上書きを許可し、個別テストが完全な kwargs を貼り付けずに
  特定の境界値を検証できるようにする。
* 生成したインスタンスを :data:`_SYNTHETIC_REGISTRY` に登録し、
  :func:`is_synthetic` で後から「ファクトリ由来か」を確認できるようにする。

``WeakValueDictionary`` をインラインメタデータより優先する理由:

* :class:`bakufu.domain.empire.Empire`、:class:`RoomRef`、:class:`AgentRef`
  は ``frozen=True`` で ``extra='forbid'`` の Pydantic v2 モデル ──
  素朴な ``_meta.synthetic`` 属性追加は物理的に不可能。
* ``id(instance)`` をキーとする弱参照レジストリは外側からインスタンスに
  フラグ付けする。値が GC されるとエントリは自動失効するので、無関係な
  新規 allocate で ``id`` が再利用されても false positive ではなく
  キャッシュミスとなる。

本モジュールを本番コードから import してはならない ── 合成データ境界を
監査可能に保つため ``tests/`` 配下に配置されている。
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4
from weakref import WeakValueDictionary

from bakufu.domain.empire import Empire
from bakufu.domain.value_objects import AgentRef, Role, RoomRef
from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Sequence

# モジュールスコープのレジストリ。値は弱参照で保持するので GC 圧は中立 ──
# 「このオブジェクトはファクトリ由来か」をオブジェクト生存中だけ知ればよい。
_SYNTHETIC_REGISTRY: WeakValueDictionary[int, BaseModel] = WeakValueDictionary()


def is_synthetic(instance: BaseModel) -> bool:
    """``instance`` が本モジュールのファクトリで生成されたものなら ``True`` を返す。

    検査は構造的ではなく ID ベース (``id``)。これにより独立に生成された
    等値の 2 インスタンスは区別される ── ファクトリが返した実オブジェクトのみ
    合成印が付く。
    """
    cached = _SYNTHETIC_REGISTRY.get(id(instance))
    return cached is instance


def _register(instance: BaseModel) -> None:
    """``instance`` を合成レジストリに記録する。"""
    _SYNTHETIC_REGISTRY[id(instance)] = instance


# ---------------------------------------------------------------------------
# RoomRef ファクトリ
# ---------------------------------------------------------------------------
def make_room_ref(
    *,
    room_id: UUID | None = None,
    name: str = "ルーム",
    archived: bool = False,
) -> RoomRef:
    """妥当な :class:`RoomRef` を構築し合成印を付ける。"""
    ref = RoomRef(
        room_id=room_id if room_id is not None else uuid4(),
        name=name,
        archived=archived,
    )
    _register(ref)
    return ref


# ---------------------------------------------------------------------------
# AgentRef ファクトリ
# ---------------------------------------------------------------------------
def make_agent_ref(
    *,
    agent_id: UUID | None = None,
    name: str = "エージェント",
    role: Role = Role.DEVELOPER,
) -> AgentRef:
    """妥当な :class:`AgentRef` を構築し合成印を付ける。"""
    ref = AgentRef(
        agent_id=agent_id if agent_id is not None else uuid4(),
        name=name,
        role=role,
    )
    _register(ref)
    return ref


# ---------------------------------------------------------------------------
# Empire ファクトリ
# ---------------------------------------------------------------------------
def make_empire(
    *,
    empire_id: UUID | None = None,
    name: str = "テスト幕府",
    rooms: Sequence[RoomRef] | None = None,
    agents: Sequence[AgentRef] | None = None,
) -> Empire:
    """妥当な :class:`Empire` を構築し合成印を付ける。

    上書きなしの場合、room / agent なしの空 Empire を返す ── 最小妥当な
    aggregate 状態。これは公開 behavior (``hire_agent`` / ``establish_room``
    / ``archive_room``) で変更する大多数のテストに適している。
    """
    empire = Empire(
        id=empire_id if empire_id is not None else uuid4(),
        name=name,
        rooms=list(rooms) if rooms is not None else [],
        agents=list(agents) if agents is not None else [],
    )
    _register(empire)
    return empire


def make_populated_empire(
    *,
    empire_id: UUID | None = None,
    name: str = "テスト幕府",
    n_rooms: int = 2,
    n_agents: int = 3,
) -> Empire:
    """Repository ラウンドトリップテスト用に N rooms + M agents の Empire を構築する。

    Empire-Repository PR (#25) は §確定 B delete-then-insert フローを
    検証するために本ファクトリを必要とする ── 空 Empire は ``empires``
    テーブルのみを触るが、populated Empire は 3 テーブル全て
    (empires + empire_room_refs + empire_agent_refs) に書く。これにより
    side テーブルが実際にバルク INSERT を受けることをテストでアサートできる。

    role は DEVELOPER / TESTER / REVIEWER を巡回する ── 3 agent の Empire は
    3 つの別 Role enum 値を網羅する。
    """
    rooms = [make_room_ref(name=f"ルーム{i + 1}") for i in range(n_rooms)]
    role_cycle = [Role.DEVELOPER, Role.TESTER, Role.REVIEWER]
    agents = [
        make_agent_ref(name=f"エージェント{i + 1}", role=role_cycle[i % len(role_cycle)])
        for i in range(n_agents)
    ]
    return make_empire(
        empire_id=empire_id,
        name=name,
        rooms=rooms,
        agents=agents,
    )


__all__ = [
    "is_synthetic",
    "make_agent_ref",
    "make_empire",
    "make_populated_empire",
    "make_room_ref",
]
