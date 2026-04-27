"""Archive idempotency (REQ-AG-005 / Confirmation D).

Covers TC-UT-AG-010 / 020 / 025. The contract that ``archive()`` always
returns a *new* instance is verified explicitly with ``is`` comparison so
that future "skip if already archived" optimizations cannot reintroduce
identity-based caching without breaking these tests.
"""

from __future__ import annotations

from tests.factories.agent import make_agent, make_archived_agent


class TestArchiveBasic:
    """TC-UT-AG-010 — archive flips archived=True."""

    def test_archive_returns_archived_true(self) -> None:
        """TC-UT-AG-010: archive() flips archived to True on the returned Agent."""
        agent = make_agent()
        archived = agent.archive()
        assert archived.archived is True

    def test_archive_does_not_mutate_original(self) -> None:
        """TC-UT-AG-010: original Agent stays archived=False."""
        agent = make_agent()
        agent.archive()
        assert agent.archived is False


class TestArchiveIdempotency:
    """TC-UT-AG-020 / 025 — idempotency = state equality, NOT object identity."""

    def test_archive_on_already_archived_does_not_raise(self) -> None:
        """TC-UT-AG-020: archive() on archived=True Agent succeeds (no exception)."""
        agent = make_archived_agent()
        result = agent.archive()  # must not raise
        assert result.archived is True

    def test_archive_on_already_archived_returns_new_instance(self) -> None:
        """TC-UT-AG-020 / Confirmation D: archive() ALWAYS returns a new instance.

        ``a1 is a2`` must be False — Confirmation D forbids object-identity
        caching. Idempotency is defined as "result state matches", proven by
        the structural-equality assertion in the next test.
        """
        agent = make_archived_agent()
        result = agent.archive()
        assert result is not agent

    def test_archive_on_already_archived_is_structurally_equal(self) -> None:
        """TC-UT-AG-020: result of redundant archive() is == the original archived Agent."""
        agent = make_archived_agent()
        result = agent.archive()
        assert result == agent  # same fields, different identity

    def test_three_consecutive_archive_calls_yield_archived_true(self) -> None:
        """TC-UT-AG-025: archive().archive().archive() all keep archived=True."""
        agent = make_agent()
        a1 = agent.archive()
        a2 = a1.archive()
        a3 = a2.archive()
        assert a1.archived is True and a2.archived is True and a3.archived is True

    def test_three_consecutive_archive_calls_each_yield_distinct_instance(self) -> None:
        """TC-UT-AG-025: each archive() call returns a distinct object identity."""
        agent = make_agent()
        a1 = agent.archive()
        a2 = a1.archive()
        a3 = a2.archive()
        assert a1 is not a2 and a2 is not a3 and a1 is not a3
