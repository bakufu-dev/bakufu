"""ExternalReviewGate 集約ルートのテスト。トピック別に分割している。

``docs/features/external-review-gate/test-design.md`` および empire-repository
PR #29 の教訓（Norman 500 行ルール）に従い、テスト面を初期から 4 つの兄弟
モジュールに分割している:

* :mod:`...test_construction` — TC-UT-GT-001 / 002 / 012（コンストラクタ、
  4 種の ReviewDecision の再構成、frozen + 構造的等価性）。
* :mod:`...test_state_machine` — TC-UT-GT-003 / 004 / 005 / 006 / 013 /
  014 / 015（4x4 = 16 セルのディスパッチ: 7 件の正常遷移、9 件の
  decision_already_decided セル、テーブル不変性、pre-validate 失敗時に
  ソースを変更しないこと、ライフサイクルシナリオ）。
* :mod:`...test_invariants` — TC-UT-GT-007 / 008 / 009 / 010 / 011 /
  021〜025（5 種のバリデータ、4 種の改ざんパターン、スナップショット三重防御、
  自動マスキング、MSG 2 行の "Next:" ヒントの物理的保証）。
* :mod:`...test_vo` — AuditEntry / ReviewDecision / AuditAction の Enum と
  VO の frozen 性および NFC 正規化。

M1 の 7 番目の兄弟モジュール — M1 最終ピース。ファクトリは
``tests/factories/external_review_gate.py`` に存在する。
"""
