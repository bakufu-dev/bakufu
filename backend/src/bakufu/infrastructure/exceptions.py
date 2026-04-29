"""インフラストラクチャ層の例外。

Bootstrap の各 Stage およびマスキング ゲートウェイから送出される。
``docs/features/persistence-foundation/detailed-design/messages.md`` の
MSG-PF-001〜008 と 1:1 で対応する。

* :class:`BakufuConfigError` — DATA_DIR / engine / migration / FS 初期化の
  失敗（MSG-PF-001 / 002 / 003 / 008）。Bootstrap が捕捉し、非ゼロ終了する。
* :class:`BakufuMigrationError` — Alembic ``upgrade`` 失敗（MSG-PF-004）。
  :class:`BakufuConfigError` のサブクラスとし、Bootstrap トップレベルの
  ``except`` で従来どおり捕捉できるようにしつつ、ログのフィルタリングを
  可能にしている。
* :class:`HandlerNotRegisteredError` — Outbox ハンドラレジストリに該当
  event_kind のハンドラが登録されていない場合に送出される。Outbox
  ディスパッチャは本例外を捕捉して WARN を出し、対象行を ``status='PENDING'``
  に戻す。
"""

from __future__ import annotations


class BakufuConfigError(Exception):
    """インフラストラクチャ設定が確立できない場合に送出される。

    :attr:`msg_id` に MSG-PF-NNN 識別子を保持するため、下流のログ
    フォーマッタやテストアサーションは自由形式の文字列を解析せずに、
    特定の失敗ケースで分岐できる。
    """

    def __init__(self, *, msg_id: str, message: str) -> None:
        super().__init__(message)
        self.msg_id: str = msg_id
        self.message: str = message


class BakufuMigrationError(BakufuConfigError):
    """Alembic ``upgrade`` 失敗（MSG-PF-004）。

    :class:`BakufuConfigError` を継承するため、Bootstrap ループの
    トップレベル ``except`` でそのまま捕捉できる。一方でテスト時に
    マイグレーション固有の問題のみフィルタする能力も維持できる。
    """


class HandlerNotRegisteredError(KeyError):
    """:class:`HandlerRegistry.resolve` でハンドラが見つからない際に送出。

    :class:`KeyError` を継承するため、汎用的に「キー不在」を扱う呼び出し
    側コードはそのまま素直に縮退する。Outbox ディスパッチャは本例外を
    捕捉し、対象行を ``PENDING`` として次サイクルにマークし直す。
    """


__all__ = [
    "BakufuConfigError",
    "BakufuMigrationError",
    "HandlerNotRegisteredError",
]
