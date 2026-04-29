"""Directive アグリゲートルートのファクトリ群.

``docs/features/directive/test-design.md`` 準拠。
empire / workflow / agent / room と同パターン: 各ファクトリは本番
コンストラクタ経由で *妥当* なデフォルトインスタンスを返し、キーワード
上書きを許可し、結果を :class:`WeakValueDictionary` に登録する。これにより
:func:`is_synthetic` が後から、frozen Pydantic モデルを変更せずに
テスト由来オブジェクトをフラグ付けできる。

デフォルト Directive は短い ``text`` 本文と ``task_id=None`` を持つ。
``LinkedDirectiveFactory`` は post-link 状態を直接構築する
(Repository ハイドレートシナリオ、§確定 C)。``LongTextDirectiveFactory`` は
上限境界 (10000 文字) にある。
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4
from weakref import WeakValueDictionary

from bakufu.domain.directive import Directive
from pydantic import BaseModel

# モジュールスコープのレジストリ。値は弱参照で GC 圧は中立に保つ。
_SYNTHETIC_REGISTRY: WeakValueDictionary[int, BaseModel] = WeakValueDictionary()


def is_synthetic(instance: BaseModel) -> bool:
    """``instance`` が本モジュールのファクトリで生成されたものなら ``True`` を返す。"""
    cached = _SYNTHETIC_REGISTRY.get(id(instance))
    return cached is instance


def _register(instance: BaseModel) -> None:
    """``instance`` を合成レジストリに記録する。"""
    _SYNTHETIC_REGISTRY[id(instance)] = instance


def make_directive(
    *,
    directive_id: UUID | None = None,
    text: str = "$ ブログ分析機能を作って",
    target_room_id: UUID | None = None,
    created_at: datetime | None = None,
    task_id: UUID | None = None,
) -> Directive:
    """妥当な :class:`Directive` を構築する。

    デフォルト: アプリケーション層が正規化していたであろう ``$`` プレフィックス
    を含む短い ``text``、``task_id=None`` (まだ link されていない)、
    ``created_at=datetime.now(UTC)`` ── テストごとのセットアップなしに
    tz-aware 制約を満たすため。
    """
    directive = Directive(
        id=directive_id if directive_id is not None else uuid4(),
        text=text,
        target_room_id=target_room_id if target_room_id is not None else uuid4(),
        created_at=created_at if created_at is not None else datetime.now(UTC),
        task_id=task_id,
    )
    _register(directive)
    return directive


def make_linked_directive(
    *,
    directive_id: UUID | None = None,
    text: str = "$ 既に紐付け済みの directive",
    target_room_id: UUID | None = None,
    task_id: UUID | None = None,
) -> Directive:
    """既に非 ``None`` の ``task_id`` を持つ Directive を構築する。

    Repository ハイドレートシナリオ (§確定 C): コンストラクタは永続的な
    ``task_id`` 値を受理し、既に link 済みの Directive をディスクから
    復元する。返却インスタンスに対して ``link_task`` を呼ぶと Fail Fast する。
    """
    return make_directive(
        directive_id=directive_id,
        text=text,
        target_room_id=target_room_id,
        task_id=task_id if task_id is not None else uuid4(),
    )


def make_long_text_directive() -> Directive:
    """上限境界 (NFC 10000 文字) の Directive を構築する。"""
    return make_directive(text="a" * 10_000)


__all__ = [
    "is_synthetic",
    "make_directive",
    "make_linked_directive",
    "make_long_text_directive",
]
