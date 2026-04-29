"""Declarative ベース + 横断的な :class:`TypeDecorator` アダプタ。

bakufu の SQLite スキーマに含まれるすべてのテーブルは :class:`Base`
（以下で再エクスポート）を継承する。ここで定義するカスタムカラム型は、
対応する意味値を保持する任意のテーブルにとって **必須** である:

* :class:`UUIDStr` — ``uuid.UUID`` を SQLite 上で 32 文字の 16 進文字列
  として保存する（SQLite はネイティブな UUID 型を持たない。``BLOB(16)``
  は ``sqlite3`` CLI でのデバッグ性を損なうため却下した）。
* :class:`UTCDateTime` — naive な ``datetime`` を Fail-Fast で拒否し、
  UTC ISO-8601 文字列として保存する。「常に tz-aware」契約により、
  下流コードの「これは UTC？ローカル？」というバグを根絶する。
* :class:`JSONEncoded` — ``dict`` / ``list`` → ``json.dumps`` を
  ``sort_keys=True`` で実行するため、論理的に等しいペイロードは
  行内でバイト等価になる。
* :class:`MaskedJSONEncoded` / :class:`MaskedText` — 上記の派生で、
  JSON エンコード／永続化の *前* にすべての bound 値をマスキング
  ゲートウェイ経由にする（BUG-PF-001 の修正）。``process_bind_param``
  フックは ORM の ``Session.add()`` フラッシュと Core の
  ``insert(table).values(...)`` の両経路で発火するため、行が
  どのように engine に到達してもマスキングは強制される。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CHAR, Dialect, Text, TypeDecorator
from sqlalchemy.orm import DeclarativeBase

from bakufu.infrastructure.security.masking import (
    REDACT_LISTENER_ERROR,
    mask,
    mask_in,
)


class Base(DeclarativeBase):
    """bakufu の SQLite テーブル全てに共通の Declarative ベース。"""


class UUIDStr(TypeDecorator[UUID]):
    """:class:`uuid.UUID` を SQLite 上で ``CHAR(32)`` の 16 進文字列として保存する。

    32 文字の 16 進形式（ハイフンなし）はストレージをコンパクトに保ちつつ、
    ``sqlite3`` CLI から自明に確認可能なまま維持する。``uuid.UUID`` で
    ラウンドトリップするので、ORM 側コードは文字列表現を見ない。
    """

    impl = CHAR(32)
    cache_ok = True

    def process_bind_param(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        value: UUID | str | None,
        dialect: Dialect,
    ) -> str | None:
        del dialect  # 未使用。ターゲットは SQLite のみ
        if value is None:
            return None
        if isinstance(value, UUID):
            return value.hex
        # 生 SQL からのアドホックな INSERT もクリーンにラウンドトリップ
        # できるよう、str 入力も受け付ける。``UUID(str)`` がフォーマットを検証する。
        return UUID(value).hex

    def process_result_value(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        value: str | None,
        dialect: Dialect,
    ) -> UUID | None:
        del dialect
        if value is None:
            return None
        return UUID(value)


class UTCDateTime(TypeDecorator[datetime]):
    """常に UTC・常に tz-aware な ``datetime`` カラム。

    naive な ``datetime`` を渡すと即座に ``ValueError`` を送出するので、
    タイムゾーン関連のバグが静かに紛れ込むことはない。ディスク上の表現は
    ``+00:00`` オフセット付きの ISO-8601 で、文字列としてソート可能。
    """

    impl = Text()
    cache_ok = True

    def process_bind_param(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        value: datetime | None,
        dialect: Dialect,
    ) -> str | None:
        del dialect
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(
                "UTCDateTime requires a timezone-aware datetime (received a naive value)"
            )
        return value.isoformat()

    def process_result_value(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        value: str | None,
        dialect: Dialect,
    ) -> datetime | None:
        del dialect
        if value is None:
            return None
        return datetime.fromisoformat(value)


class JSONEncoded(TypeDecorator[Any]):
    """``dict`` / ``list`` ↔ JSON テキストカラム。

    ``sort_keys=True`` を使うので、意味的に等しい 2 つのペイロードは
    バイト等価なテキストにシリアライズされる — ハッシュ比較や
    マイグレーション diff にとって重要。``ensure_ascii=False`` により、
    SQLite を直接覗いたときに日本語文字列が読みやすくなる。
    """

    impl = Text()
    cache_ok = True

    def process_bind_param(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        value: object,
        dialect: Dialect,
    ) -> str | None:
        del dialect
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    def process_result_value(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        value: str | None,
        dialect: Dialect,
    ) -> object:
        del dialect
        if value is None:
            return None
        return json.loads(value)


class MaskedJSONEncoded(TypeDecorator[Any]):
    """秘密情報のマスキング付き ``dict`` / ``list`` ↔ JSON テキストカラム。

    ``json.dumps`` の前に bound 値を :func:`mask_in` に通す。
    ``process_bind_param`` は ORM フラッシュによる insert と
    Core の ``insert(table).values(...)`` の **両方** で発火する
    （BUG-PF-001 の修正）。これにより本クラスは真のゲートウェイとなり、
    呼び出し側がリダクションをバイパスする構文を選ぶ余地はない。

    確定 F（Fail-Secure）: :func:`mask_in` 自身が例外を送出した場合、
    生のバイト列をディスクに到達させずペイロード全体を listener-error の
    sentinel に置き換える。
    """

    impl = Text()
    cache_ok = True

    def process_bind_param(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        value: object,
        dialect: Dialect,
    ) -> str | None:
        del dialect
        if value is None:
            return None
        try:
            masked = mask_in(value)
        except Exception:  # pragma: no cover — Fail-Secure
            return json.dumps(REDACT_LISTENER_ERROR)
        return json.dumps(masked, ensure_ascii=False, sort_keys=True)

    def process_result_value(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        value: str | None,
        dialect: Dialect,
    ) -> object:
        del dialect
        if value is None:
            return None
        return json.loads(value)


class MaskedText(TypeDecorator[str]):
    """:func:`mask` による秘密情報のマスキング付き ``str`` テキストカラム。

    :class:`MaskedJSONEncoded` と同じゲートウェイ保証: すべての bound 値
    （ORM／Core）は永続化前にマスクされ、masker が失敗した場合は
    生文字列ではなく :data:`REDACT_LISTENER_ERROR` を返す。
    """

    impl = Text()
    cache_ok = True

    def process_bind_param(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        value: object,
        dialect: Dialect,
    ) -> str | None:
        del dialect
        if value is None:
            return None
        try:
            return mask(value)
        except Exception:  # pragma: no cover — Fail-Secure
            return REDACT_LISTENER_ERROR

    def process_result_value(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        value: str | None,
        dialect: Dialect,
    ) -> str | None:
        del dialect
        return value


__all__ = [
    "Base",
    "JSONEncoded",
    "MaskedJSONEncoded",
    "MaskedText",
    "UTCDateTime",
    "UUIDStr",
]
