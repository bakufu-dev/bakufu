"""SQLite 永続化レイヤ（:mod:`sqlalchemy.ext.asyncio` による非同期実装）。

パッケージ境界は設計上の責務分割に対応する
（``docs/features/persistence-foundation/detailed-design/`` 参照）:

* :mod:`bakufu.infrastructure.persistence.sqlite.engine` —
  PRAGMA を強制し、デュアル接続（アプリケーション用 vs マイグレーション用）
  を分離する ``AsyncEngine`` ファクトリ。
* :mod:`bakufu.infrastructure.persistence.sqlite.session` —
  ``async_sessionmaker`` ファクトリ（Unit-of-Work 境界）。
* :mod:`bakufu.infrastructure.persistence.sqlite.base` — Declarative
  ベース + UUID / UTC-aware datetime / JSON の :class:`TypeDecorator` 型群。
* :mod:`bakufu.infrastructure.persistence.sqlite.tables` —
  横断的なテーブル群（``audit_log`` / ``bakufu_pid_registry`` /
  ``domain_event_outbox``）とそのマスキングリスナ。
* :mod:`bakufu.infrastructure.persistence.sqlite.outbox` —
  Outbox dispatcher とハンドラレジストリのスケルトン。
* :mod:`bakufu.infrastructure.persistence.sqlite.pid_gc` —
  Bootstrap stage 4 の孤児プロセスガーベジコレクション。
"""
