"""SQLite リポジトリ アダプタ（Aggregate ごとに 1 モジュール）。

各モジュールは :mod:`bakufu.application.ports` で定義される対応する
:class:`typing.Protocol` を満たすクラスをエクスポートする。Empire（PR #25）が
最初のリポジトリ PR。同じパターンが後続の ``feature/{aggregate}-repository``
PR に適用される:

* ``__init__(session: AsyncSession)`` — 呼び元管理の Tx 境界を保つ
  （リポジトリは ``session.commit()`` / ``session.rollback()`` を呼ばない）。
* ``find_by_id`` / ``count`` / ``save`` は ``async def``。
* 関連／子テーブルは呼び元のトランザクション内で delete-then-insert
  （§確定 B）により更新される。
* ``_to_row`` / ``_from_row`` はプライベートで、ドメイン Aggregate Root と
  ``dict`` ペイロード間を変換する（§確定 C）。
"""
