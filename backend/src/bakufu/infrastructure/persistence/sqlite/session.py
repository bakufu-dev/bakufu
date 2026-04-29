"""``async_sessionmaker`` ファクトリ（Unit-of-Work 境界）。

Aggregate リポジトリはここで作成されたファクトリから :class:`AsyncSession`
を取得する。各 ``async with session.begin():`` ブロックが 1 Unit-of-Work を
構成する。セッションは明示フラッシュ（``autoflush=False``）に設定する。
これによりリスナ駆動のマスキングが行書き込みごとに正確に 1 回適用される —
read クエリ内部で自動フラッシュすると誰も望まない曖昧さが生じる。
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


def make_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """``engine`` 用のセッション ファクトリを構築する。

    Args:
        engine: :func:`bakufu.infrastructure.persistence.sqlite.engine.create_engine`
            から得るアプリケーション レベルのエンジン。

    ファクトリは async で、``expire_on_commit=False``（コミット境界を跨いでも
    ドメイン オブジェクトが生き続けるよう）、``autoflush=False``（マスキング
    リスナが予測可能になるよう）。
    """
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


__all__ = ["make_session_factory"]
