"""bakufu Backend 向けの永続化ドライバ（SQLite + Alembic）。

このパッケージのトップは意図的に薄い: 唯一のストレージ対象は SQLite で
あり（``docs/design/tech-stack.md`` §DB 参照）、``sqlite/`` サブパッケージが
engine / session / base / table の各モジュールを保持する。「将来の
Postgres 対応」のための抽象層は YAGNI として導入していない。Aggregate
固有の Repository 実装は各機能 PR（``feature/{aggregate}-repository``）に
配置する。本パッケージは横断的なテーブル ``audit_log`` /
``bakufu_pid_registry`` / ``domain_event_outbox`` のみ提供する。
"""
