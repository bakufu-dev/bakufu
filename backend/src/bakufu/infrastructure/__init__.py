"""bakufu インフラストラクチャ層。

I/O が中心となるコードを集約する: SQLite + Alembic 永続化、シークレット
マスキング ゲートウェイ、OS 寄りの設定（DATA_DIR / pid_registry GC）、および
Backend の Bootstrap シーケンス。依存方向は **厳密に** ``domain → no one`` /
``infrastructure → domain``: ドメイン側のコードは本パッケージから
import してはならない。テストスイート
``tests/architecture/test_dependency_direction.py`` がこの契約を強制する。

詳細設計は ``docs/features/persistence-foundation`` を参照。
"""
