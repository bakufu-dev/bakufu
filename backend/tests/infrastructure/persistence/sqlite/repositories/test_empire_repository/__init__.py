"""Empire Repository integration tests, split by topic.

Per ``docs/features/empire-repository/test-design.md`` and Norman's
500-line rule: the original ``test_empire_repository.py`` (506 lines)
is split into three siblings so each file stays under the readability
budget and the next 6 Repository PRs can extend the pattern without
inheriting a 500+ line monolith:

* :mod:`...test_protocol_crud` — Protocol surface + ``find_by_id`` /
  ``count`` / ``save`` basic CRUD (TC-IT-EMR-001〜005, 010, 018).
* :mod:`...test_save_semantics` — delete-then-insert + Tx boundary
  + round-trip equality (TC-IT-EMR-006, 007, 011, 012 + TC-UT-EMR-003).
* :mod:`...test_constraints_arch` — DB-level FK CASCADE + UNIQUE +
  CI three-layer-defense template structure (TC-IT-EMR-013, 014, 017).
"""
