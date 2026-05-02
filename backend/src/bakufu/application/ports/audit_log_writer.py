"""AuditLogWriterPort — audit_log 追記 Port（admin-cli 用）。

AdminService の全 public メソッドが操作の成否に依らず audit_log を記録するために
使う Clean Architecture Port（§確定 A / §確定 D）。

SQLAlchemy の直接 import を application 層に持ち込まない（依存方向保全）。

設計書: docs/features/admin-cli/application/detailed-design.md
"""

from __future__ import annotations

from typing import Protocol


class AuditLogWriterPort(Protocol):
    """audit_log 追記の Port 契約（Admin CLI 用）。

    infrastructure 実装:
      ``bakufu.infrastructure.persistence.sqlite.repositories.audit_log_writer``

    全メソッドは async。
    """

    async def write(
        self,
        actor: str,
        command: str,
        args_json: dict[str, object],
        result: str,
        error_text: str | None = None,
    ) -> None:
        """audit_log テーブルに 1 行追記する。

        Args:
            actor: OS ユーザー名（``getpass.getuser()`` 相当、CLI 起動時に DI）。
            command: 実行コマンド名（例: ``'list-blocked'``）。
            args_json: 実行引数（識別子のみ。raw テキスト禁止 §確定 A）。
            result: ``'OK'`` または ``'FAIL'`` の 2 値。
            error_text: 失敗時のマスキング済み例外メッセージ（成功時は None）。

        Raises:
            Exception: 書き込み失敗時は例外を握り潰さず再 raise する。
                audit_log の欠落は許容しない（§確定 A）。
        """
        ...


__all__ = ["AuditLogWriterPort"]
