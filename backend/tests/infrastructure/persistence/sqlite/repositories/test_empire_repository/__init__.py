"""トピックごとに分割された Empire Repository の統合テスト群。

``docs/features/empire-repository/test-design.md`` および Norman の
500 行ルールに従い、元の ``test_empire_repository.py``（506 行）を
3 つの兄弟ファイルに分割している。各ファイルは可読性の閾値を超えず、
後続の 6 Repository PR が 500+ 行のモノリスを継承することなく
同じパターンを拡張できる:

* :mod:`...test_protocol_crud` — Protocol 面 + ``find_by_id`` /
  ``count`` / ``save`` の基本 CRUD（TC-IT-EMR-001〜005, 010, 018）。
* :mod:`...test_save_semantics` — delete-then-insert + Tx 境界
  + ラウンドトリップ等価性（TC-IT-EMR-006, 007, 011, 012 + TC-UT-EMR-003）。
* :mod:`...test_constraints_arch` — DB レベルの FK CASCADE + UNIQUE +
  CI 三層防衛テンプレート構造（TC-IT-EMR-013, 014, 017）。
"""
