"""Task 集約ルートのテスト。トピック別に分割している。

``docs/features/task/test-design.md`` および empire-repository PR #29 の
教訓（Norman 500 行ルール）に従い、各ファイルが可読性の上限を超えないよう、
初期からテスト面を 4 つの兄弟モジュールに分割している:

* :mod:`...test_construction` — TC-UT-TS-001 / 002 / 014 / 040 /
  044 / 045 / 053（コンストラクタ、frozen、NFC、型エラー）。
* :mod:`...test_state_machine` — TC-UT-TS-003〜008, 030〜035, 038,
  039 + TC-IT-TS-001〜005（60 セルのディスパッチテーブル、13 遷移、
  20 終端セル、ライフサイクル統合シナリオ）。
* :mod:`...test_invariants` — TC-UT-TS-009〜011, 041〜043, 046〜052
  （5 種のバリデータ、自動マスキング、Next: ヒントの物理的保証）。
* :mod:`...test_vo` — TC-UT-TS-012, 013, 036, 037（Deliverable と
  Attachment の 6 段階サニタイズおよび Enum）。
"""
