"""Agent Repository integration tests, split by topic.

Per ``docs/features/agent-repository/test-design.md`` and the
empire-repository PR #29 教訓 (Norman 500-line rule), the test
surface is split into four siblings so each file stays under the
readability budget:

* :mod:`...test_protocol_crud` — Protocol surface (4 methods) +
  ``find_by_id`` / ``count`` / ``find_by_name`` basic CRUD
  (TC-UT-AGR-001 / 004 / 005).
* :mod:`...test_save_semantics` — delete-then-insert + 5-step SQL
  order + ORDER BY contract + Tx boundary + round-trip equality
  (TC-UT-AGR-002 / 003 / 010 / 011).
* :mod:`...test_constraints_arch` — DB-level partial unique index
  二重防衛 + Alembic 0004 + arch-test reference
  (TC-IT-AGR-007 / 008 / TC-UT-AGR-009).
* :mod:`...test_masking_persona` — **Schneier #3 实適用 7 経路**:
  Anthropic / GitHub / OpenAI / Bearer / no-secret / roundtrip /
  multiple — verifies via raw-SQL SELECT that ``agents.prompt_body``
  carries ``<REDACTED:*>`` and zero raw token bytes
  (TC-IT-AGR-006-masking-*).
"""
