"""トピックごとに分割された Agent Repository の統合テスト群。

``docs/features/agent-repository/test-design.md`` および
empire-repository PR #29 の教訓（Norman の 500 行ルール）に従い、
各ファイルが可読性の閾値を超えないようにテスト面を 4 つの兄弟ファイル
に分割している:

* :mod:`...test_protocol_crud` — Protocol 面（4 メソッド）+
  ``find_by_id`` / ``count`` / ``find_by_name`` の基本 CRUD
  （TC-UT-AGR-001 / 004 / 005）。
* :mod:`...test_save_semantics` — delete-then-insert + 5 ステップ SQL
  順序 + ORDER BY 契約 + Tx 境界 + ラウンドトリップ等価性
  （TC-UT-AGR-002 / 003 / 010 / 011）。
* :mod:`...test_constraints_arch` — DB レベルの部分 unique index による
  二重防衛 + Alembic 0004 + arch-test リファレンス
  （TC-IT-AGR-007 / 008 / TC-UT-AGR-009）。
* :mod:`...test_masking_persona` — **Schneier #3 実適用 7 経路**:
  Anthropic / GitHub / OpenAI / Bearer / no-secret / roundtrip /
  multiple — raw-SQL SELECT を通じて ``agents.prompt_body`` が
  ``<REDACTED:*>`` を保持しトークン生バイトを含まないことを検証
  （TC-IT-AGR-006-masking-*）。
"""
