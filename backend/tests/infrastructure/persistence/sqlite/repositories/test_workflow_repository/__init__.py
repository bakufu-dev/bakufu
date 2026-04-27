"""Workflow Repository integration tests, split by topic.

Per ``docs/features/workflow-repository/test-design.md`` and Norman's
500-line rule (established in empire-repository PR #25): the test
surface is split into four siblings so each file stays under the
readability budget and the next 5 Repository PRs can extend the
pattern without inheriting a 500+ line monolith:

* :mod:`...test_protocol_crud` — Protocol surface + ``find_by_id`` /
  ``count`` / ``save`` basic CRUD + ORDER BY observation + COUNT(*) SQL
  observation + singleton non-enforcement
  (TC-IT-WFR-001〜007, 019).
* :mod:`...test_save_semantics` — delete-then-insert + 5-step SQL
  order + Tx boundary + roles_csv determinism + round-trip equality
  (TC-IT-WFR-008〜012, 015, 016).
* :mod:`...test_constraints_arch` — DB-level FK CASCADE + UNIQUE pair
  enforcement + CI three-layer-defense partial-mask template
  (TC-IT-WFR-017, 018, 023).
* :mod:`...test_masking` — §確定 H 物理確認: ``MaskedJSONEncoded``
  redaction at the SQLite layer + §不可逆性 (find_by_id raises on
  masked notify_channels) (TC-IT-WFR-013, 014).
"""
