"""Application-layer responsibility boundary tests (TC-UT-DR-018 / 019).

Confirmation G / H freeze that **Aggregate-internal invariants are
structural only**: ``text`` length and ``task_id`` uniqueness. Cross-
aggregate concerns (``target_room_id`` Room existence, ``$``-prefix
normalization, Workflow resolution, Task creation in 1 Tx) live in
``DirectiveService.issue()`` because they require external knowledge.
These tests freeze that boundary so a future refactor cannot silently
push aggregate-level checks into Directive (the regression direction
Norman / Steve worked hard to keep clean for agent / room).
"""

from __future__ import annotations

from uuid import uuid4

from tests.factories.directive import make_directive


class TestTargetRoomIdReferentialIntegrityNotEnforcedByAggregate:
    """TC-UT-DR-018: Aggregate accepts any UUID as ``target_room_id``."""

    def test_arbitrary_room_id_constructs(self) -> None:
        """TC-UT-DR-018: Room existence is verified by DirectiveService, not Directive."""
        # The UUID is arbitrary — no Room with this id exists. Aggregate
        # accepts because referential integrity is application-layer scope.
        directive = make_directive(target_room_id=uuid4())
        assert directive.target_room_id is not None


class TestDollarPrefixNotNormalizedByAggregate:
    """TC-UT-DR-019: Aggregate stores ``text`` verbatim — no ``$`` prefix injection."""

    def test_text_without_dollar_prefix_constructs_unchanged(self) -> None:
        """TC-UT-DR-019: ``$`` prefix normalization is DirectiveService responsibility.

        ``DirectiveService.issue(raw_text)`` is the layer that ensures
        ``text`` starts with ``$``. The Aggregate trusts the input
        verbatim — same pattern Agent §確定 I uses for ``provider_kind``
        MVP gating.
        """
        # No ``$`` prefix in the input — Aggregate keeps the text as-is.
        directive = make_directive(text="ブログ分析機能を作って")
        assert not directive.text.startswith("$")
        assert directive.text == "ブログ分析機能を作って"
