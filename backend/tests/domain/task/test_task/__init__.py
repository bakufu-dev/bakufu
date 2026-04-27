"""Task Aggregate Root tests, split by topic.

Per ``docs/features/task/test-design.md`` and the empire-repository
PR #29 教訓 (Norman 500-line rule), the test surface is split into
four siblings from day one so each file stays under the readability
budget:

* :mod:`...test_construction` — TC-UT-TS-001 / 002 / 014 / 040 /
  044 / 045 / 053 (constructor, frozen, NFC, type errors).
* :mod:`...test_state_machine` — TC-UT-TS-003〜008, 030〜035, 038,
  039 + TC-IT-TS-001〜005 (60-cell dispatch table, 13 transitions,
  20 terminal cells, lifecycle integration scenarios).
* :mod:`...test_invariants` — TC-UT-TS-009〜011, 041〜043, 046〜052
  (5 validators, auto-mask, Next: hint physical guarantee).
* :mod:`...test_vo` — TC-UT-TS-012, 013, 036, 037 (Deliverable +
  Attachment 6-step sanitize + enums).
"""
