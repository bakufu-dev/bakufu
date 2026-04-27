"""ExternalReviewGate Aggregate Root tests, split by topic.

Per ``docs/features/external-review-gate/test-design.md`` and the
empire-repository PR #29 教訓 (Norman 500-line rule), the test
surface is split into four siblings from day one:

* :mod:`...test_construction` — TC-UT-GT-001 / 002 / 012 (constructor,
  4 ReviewDecision rehydrations, frozen + structural equality).
* :mod:`...test_state_machine` — TC-UT-GT-003 / 004 / 005 / 006 / 013 /
  014 / 015 (4x4 = 16-cell dispatch: 7 ✓ transitions, 9 ✗
  decision_already_decided cells, table immutability, pre-validate
  fails leave source unchanged, lifecycle scenarios).
* :mod:`...test_invariants` — TC-UT-GT-007 / 008 / 009 / 010 / 011 /
  021〜025 (5 validators, 4 改ざんパターン, snapshot triple-defense,
  auto-mask, MSG 2-line "Next:" hint physical guarantee).
* :mod:`...test_vo` — AuditEntry / ReviewDecision / AuditAction
  enums + VO frozen + NFC normalization.

M1 7th sibling — final M1 piece. The factories live at
``tests/factories/external_review_gate.py``.
"""
