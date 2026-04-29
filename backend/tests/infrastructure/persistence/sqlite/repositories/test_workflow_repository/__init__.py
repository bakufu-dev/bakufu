"""トピックごとに分割された Workflow Repository の統合テスト群。

``docs/features/workflow-repository/test-design.md`` および Norman の
500 行ルール（empire-repository PR #25 で確立）に従い、各ファイルが
可読性の閾値を超えず、後続の 5 Repository PR が 500+ 行のモノリスを
継承することなくパターンを拡張できるよう、テスト面を 4 つの兄弟ファイル
に分割している:

* :mod:`...test_protocol_crud` — Protocol 面 + ``find_by_id`` /
  ``count`` / ``save`` の基本 CRUD + ORDER BY 観察 + COUNT(*) SQL 観察
  + シングルトン非強制
  （TC-IT-WFR-001〜007, 019）。
* :mod:`...test_save_semantics` — delete-then-insert + 5 ステップ SQL
  順序 + Tx 境界 + roles_csv 決定性 + ラウンドトリップ等価性
  （TC-IT-WFR-008〜012, 015, 016）。
* :mod:`...test_constraints_arch` — DB レベルの FK CASCADE + UNIQUE
  ペア強制 + CI 三層防衛部分マスクテンプレート
  （TC-IT-WFR-017, 018, 023）。
* :mod:`...test_masking` — §確定 H 物理確認: SQLite 層での
  ``MaskedJSONEncoded`` 編集 + §不可逆性（マスクされた notify_channels で
  find_by_id が例外を送出）（TC-IT-WFR-013, 014）。
"""
