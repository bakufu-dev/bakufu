"""Workflow aggregate tests, split per feature surface (Norman §file-split rule).

Tests group by Test* class topology so failures cluster by behavior:

* :mod:`test_construction` — minimal Workflow + name normalization
* :mod:`test_dag_invariants` — REQ-WF-005 (entry, reachability, sink, determinism,
  ref integrity, EXTERNAL_REVIEW notify, required_role)
* :mod:`test_mutators` — add_stage / add_transition / remove_stage + pre-validate rollback
* :mod:`test_from_dict` — bulk-import (REQ-WF-006) including T1 attack-surface
* :mod:`test_frozen_extra` — frozen=True / extra='forbid' invariants
* :mod:`test_notify_channel_ssrf` — Confirmation G G1〜G10
* :mod:`test_notify_channel_kind` — MVP `kind='discord'` constraint
* :mod:`test_notify_channel_masking` — token redaction across serialization paths
* :mod:`test_helpers_independence` — Confirmation F twin-defense direct invocation
* :mod:`test_integration` — V-model preset + lifecycle round trips
* :mod:`test_value_objects` — CompletionPolicy / NotifyChannel / Transition VO units
"""
