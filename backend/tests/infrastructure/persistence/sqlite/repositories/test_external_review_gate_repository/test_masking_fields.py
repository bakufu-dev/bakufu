"""ExternalReviewGate Repository: MaskedText wiring on 3 columns (TC-IT-ERGR-020-masking-*).

RQ-ERGR-006 / §確定 R1-E — 3 MaskedText columns physical verification:
  * external_review_gates.snapshot_body_markdown
  * external_review_gates.feedback_text
  * external_review_audit_entries.comment

Each column is verified via **raw SQL SELECT** so the observation bypasses
``MaskedText.process_result_value`` and confirms the literal bytes on disk.

9 test cases:
  snapshot_body_markdown: masked / plain / roundtrip (3 cases)
  feedback_text: masked / plain / roundtrip (3 cases)
  comment: masked / plain (2 cases)
  3-column simultaneous: 1 case

Per ``docs/features/external-review-gate-repository/test-design.md``
TC-IT-ERGR-020-masking-*.
Issue #36 — M2 0008.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from bakufu.domain.value_objects import AuditAction
from bakufu.infrastructure.persistence.sqlite.repositories.external_review_gate_repository import (
    SqliteExternalReviewGateRepository,
)
from sqlalchemy import text

from tests.factories.external_review_gate import (
    make_approved_gate,
    make_audit_entry,
    make_gate,
    make_rejected_gate,
)
from tests.factories.task import make_deliverable

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Secret token constants (real-shape, constructed to avoid push-protection)
# ---------------------------------------------------------------------------

# Discord Bot Token — [MN][A-Za-z\d]{23,}\.[\w-]{6}\.[\w-]{27,}
_DISCORD_TOKEN = "MTk4NjIyNDgz" + "NDcxOTI1MjQ4.ClFDg_." + "A" * 27
_DISCORD_SENTINEL = "<REDACTED:DISCORD_TOKEN>"

# GitHub PAT — (?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}
_GITHUB_TOKEN = "ghp_" + "X" * 40
_GITHUB_SENTINEL = "<REDACTED:GITHUB_PAT>"

# Slack Bot Token — xoxb-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24}
_SLACK_TOKEN = "xoxb-" + "1" * 11 + "-" + "2" * 11 + "-" + "A" * 24
_SLACK_SENTINEL = "<REDACTED:SLACK_TOKEN>"


# ---------------------------------------------------------------------------
# Raw-SQL helpers (bypass TypeDecorator.process_result_value)
# ---------------------------------------------------------------------------
async def _read_persisted_snapshot_body(
    session_factory: async_sessionmaker[AsyncSession],
    gate_id: UUID,
) -> str:
    """Fetch external_review_gates.snapshot_body_markdown literal bytes."""
    async with session_factory() as session:
        row = (
            await session.execute(
                text("SELECT snapshot_body_markdown FROM external_review_gates WHERE id = :id"),
                {"id": gate_id.hex},
            )
        ).first()
    if row is None:
        raise AssertionError(f"external_review_gates row not found for id={gate_id}")
    return row[0]


async def _read_persisted_feedback_text(
    session_factory: async_sessionmaker[AsyncSession],
    gate_id: UUID,
) -> str:
    """Fetch external_review_gates.feedback_text literal bytes."""
    async with session_factory() as session:
        row = (
            await session.execute(
                text("SELECT feedback_text FROM external_review_gates WHERE id = :id"),
                {"id": gate_id.hex},
            )
        ).first()
    if row is None:
        raise AssertionError(f"external_review_gates row not found for id={gate_id}")
    return row[0]


async def _read_persisted_audit_comment(
    session_factory: async_sessionmaker[AsyncSession],
    gate_id: UUID,
) -> str:
    """Fetch external_review_audit_entries.comment literal bytes (first entry)."""
    async with session_factory() as session:
        row = (
            await session.execute(
                text(
                    "SELECT comment FROM external_review_audit_entries"
                    " WHERE gate_id = :gate_id LIMIT 1"
                ),
                {"gate_id": gate_id.hex},
            )
        ).first()
    if row is None:
        raise AssertionError(f"external_review_audit_entries row not found for gate_id={gate_id}")
    return row[0]


# ---------------------------------------------------------------------------
# TC-IT-ERGR-020-masking-snapshot-masked
# ---------------------------------------------------------------------------
class TestSnapshotBodyMarkdownDiscordTokenMasked:
    """TC-IT-ERGR-020-masking-snapshot-masked: Discord token in snapshot_body_markdown redacted."""

    async def test_discord_token_in_snapshot_body_redacted_on_disk(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """Raw-SQL SELECT shows <REDACTED:DISCORD_TOKEN>; raw token absent from disk."""
        task_id, stage_id, reviewer_id = seeded_gate_context
        body = (
            f"# 設計書\nDiscord webhook: https://discord.com/api/webhooks/123/{_DISCORD_TOKEN}\n"
            f"このURLでレビュー通知を送信します。"
        )
        snapshot = make_deliverable(body_markdown=body)
        gate = make_gate(
            task_id=task_id,
            stage_id=stage_id,
            reviewer_id=reviewer_id,
            deliverable_snapshot=snapshot,
        )

        async with session_factory() as session, session.begin():
            await SqliteExternalReviewGateRepository(session).save(gate)

        persisted = await _read_persisted_snapshot_body(session_factory, gate.id)

        assert _DISCORD_SENTINEL in persisted, (
            f"[FAIL] snapshot_body_markdown missing Discord sentinel.\nPersisted: {persisted!r}"
        )
        assert _DISCORD_TOKEN not in persisted, (
            f"[FAIL] Raw Discord token leaked into snapshot_body_markdown.\n"
            f"Violates §確定 R1-E §不可逆性. Persisted: {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-ERGR-020-masking-snapshot-plain
# ---------------------------------------------------------------------------
class TestSnapshotBodyMarkdownPlainPassthrough:
    """TC-IT-ERGR-020-masking-snapshot-plain: plain text stored unchanged."""

    async def test_plain_snapshot_body_is_passthrough(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """snapshot_body_markdown without secrets stored byte-identical."""
        task_id, stage_id, reviewer_id = seeded_gate_context
        plain_body = "タスク設計が完成した。レビューをお願いします。"
        snapshot = make_deliverable(body_markdown=plain_body)
        gate = make_gate(
            task_id=task_id,
            stage_id=stage_id,
            reviewer_id=reviewer_id,
            deliverable_snapshot=snapshot,
        )

        async with session_factory() as session, session.begin():
            await SqliteExternalReviewGateRepository(session).save(gate)

        persisted = await _read_persisted_snapshot_body(session_factory, gate.id)
        assert persisted == plain_body, (
            f"[FAIL] Plain snapshot_body_markdown was modified.\n"
            f"Expected: {plain_body!r}\nGot: {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-ERGR-020-masking-snapshot-roundtrip
# ---------------------------------------------------------------------------
class TestSnapshotBodyMarkdownRoundtripIrreversible:
    """TC-IT-ERGR-020-masking-snapshot-roundtrip: find_by_id returns masked body."""

    async def test_find_by_id_returns_masked_snapshot_body(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """Save raw Discord token in snapshot_body_markdown → find_by_id → body == masked."""
        task_id, stage_id, reviewer_id = seeded_gate_context
        body = f"設計書: auth={_DISCORD_TOKEN} for Discord integration"
        snapshot = make_deliverable(body_markdown=body)
        gate = make_gate(
            task_id=task_id,
            stage_id=stage_id,
            reviewer_id=reviewer_id,
            deliverable_snapshot=snapshot,
        )

        async with session_factory() as session, session.begin():
            await SqliteExternalReviewGateRepository(session).save(gate)

        async with session_factory() as session:
            restored = await SqliteExternalReviewGateRepository(session).find_by_id(gate.id)

        assert restored is not None
        restored_body = restored.deliverable_snapshot.body_markdown
        assert _DISCORD_SENTINEL in restored_body, (
            f"[FAIL] find_by_id returned unmasked snapshot_body_markdown.\n"
            f"Restored: {restored_body!r}"
        )
        assert _DISCORD_TOKEN not in restored_body, (
            f"[FAIL] §確定 R1-E §不可逆性 violated: raw Discord token recovered.\n"
            f"Restored: {restored_body!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-ERGR-020-masking-feedback-masked
# ---------------------------------------------------------------------------
class TestFeedbackTextSlackTokenMasked:
    """TC-IT-ERGR-020-masking-feedback-masked: Slack token in feedback_text redacted."""

    async def test_slack_token_in_feedback_text_redacted_on_disk(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """Raw-SQL SELECT shows <REDACTED:SLACK_TOKEN>; raw token absent from disk."""
        task_id, stage_id, reviewer_id = seeded_gate_context
        feedback = f"レビュー承認。Slack通知: token={_SLACK_TOKEN}"
        decided_at = datetime.now(UTC)
        gate = make_rejected_gate(
            task_id=task_id,
            stage_id=stage_id,
            reviewer_id=reviewer_id,
            feedback_text=feedback,
            decided_at=decided_at,
        )

        async with session_factory() as session, session.begin():
            await SqliteExternalReviewGateRepository(session).save(gate)

        persisted = await _read_persisted_feedback_text(session_factory, gate.id)

        assert _SLACK_SENTINEL in persisted, (
            f"[FAIL] feedback_text missing Slack sentinel.\nPersisted: {persisted!r}"
        )
        assert _SLACK_TOKEN not in persisted, (
            f"[FAIL] Raw Slack token leaked into feedback_text.\n"
            f"Violates §確定 R1-E (§設計決定 ERGR-002). Persisted: {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-ERGR-020-masking-feedback-plain
# ---------------------------------------------------------------------------
class TestFeedbackTextPlainPassthrough:
    """TC-IT-ERGR-020-masking-feedback-plain: plain feedback text stored unchanged."""

    async def test_plain_feedback_text_is_passthrough(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """feedback_text without secrets stored byte-identical."""
        task_id, stage_id, reviewer_id = seeded_gate_context
        plain_feedback = "設計品質が基準を満たしていない。再提出を求める。"
        decided_at = datetime.now(UTC)
        gate = make_rejected_gate(
            task_id=task_id,
            stage_id=stage_id,
            reviewer_id=reviewer_id,
            feedback_text=plain_feedback,
            decided_at=decided_at,
        )

        async with session_factory() as session, session.begin():
            await SqliteExternalReviewGateRepository(session).save(gate)

        persisted = await _read_persisted_feedback_text(session_factory, gate.id)
        assert persisted == plain_feedback, (
            f"[FAIL] plain feedback_text was modified.\n"
            f"Expected: {plain_feedback!r}\nGot: {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-ERGR-020-masking-feedback-roundtrip
# ---------------------------------------------------------------------------
class TestFeedbackTextRoundtripIrreversible:
    """TC-IT-ERGR-020-masking-feedback-roundtrip: find_by_id returns masked feedback."""

    async def test_find_by_id_returns_masked_feedback_text(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """Save Slack token in feedback_text → find_by_id → feedback_text == masked."""
        task_id, stage_id, reviewer_id = seeded_gate_context
        feedback = f"Slack auth: {_SLACK_TOKEN} で通知を送る"
        decided_at = datetime.now(UTC)
        gate = make_approved_gate(
            task_id=task_id,
            stage_id=stage_id,
            reviewer_id=reviewer_id,
            feedback_text=feedback,
            decided_at=decided_at,
        )

        async with session_factory() as session, session.begin():
            await SqliteExternalReviewGateRepository(session).save(gate)

        async with session_factory() as session:
            restored = await SqliteExternalReviewGateRepository(session).find_by_id(gate.id)

        assert restored is not None
        assert _SLACK_SENTINEL in restored.feedback_text, (
            f"[FAIL] find_by_id returned unmasked feedback_text.\n"
            f"Restored: {restored.feedback_text!r}"
        )
        assert _SLACK_TOKEN not in restored.feedback_text, (
            f"[FAIL] §確定 R1-E §不可逆性 violated: raw Slack token recovered.\n"
            f"Restored: {restored.feedback_text!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-ERGR-020-masking-comment-masked
# ---------------------------------------------------------------------------
class TestAuditCommentGithubPatMasked:
    """TC-IT-ERGR-020-masking-comment-masked: GitHub PAT in audit comment redacted."""

    async def test_github_pat_in_audit_comment_redacted_on_disk(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """Raw-SQL SELECT shows <REDACTED:GITHUB_PAT>; raw PAT absent from disk."""
        task_id, stage_id, reviewer_id = seeded_gate_context
        comment = f"承認します。GitHub PAT: {_GITHUB_TOKEN} で変更を確認。"
        decided_at = datetime.now(UTC)
        audit_entry = make_audit_entry(
            action=AuditAction.APPROVED,
            comment=comment,
            occurred_at=decided_at,
        )
        gate = make_approved_gate(
            task_id=task_id,
            stage_id=stage_id,
            reviewer_id=reviewer_id,
            audit_trail=[audit_entry],
            decided_at=decided_at,
        )

        async with session_factory() as session, session.begin():
            await SqliteExternalReviewGateRepository(session).save(gate)

        persisted = await _read_persisted_audit_comment(session_factory, gate.id)

        assert _GITHUB_SENTINEL in persisted, (
            f"[FAIL] audit comment missing GitHub PAT sentinel.\nPersisted: {persisted!r}"
        )
        assert _GITHUB_TOKEN not in persisted, (
            f"[FAIL] Raw GitHub PAT leaked into audit_entries.comment.\n"
            f"Violates §確定 R1-E. Persisted: {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-ERGR-020-masking-comment-plain
# ---------------------------------------------------------------------------
class TestAuditCommentPlainPassthrough:
    """TC-IT-ERGR-020-masking-comment-plain: plain comment stored unchanged."""

    async def test_plain_audit_comment_is_passthrough(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """audit_entries.comment without secrets stored byte-identical."""
        task_id, stage_id, reviewer_id = seeded_gate_context
        plain_comment = "設計品質が基準を満たしている。承認する。"
        decided_at = datetime.now(UTC)
        audit_entry = make_audit_entry(
            action=AuditAction.APPROVED,
            comment=plain_comment,
            occurred_at=decided_at,
        )
        gate = make_approved_gate(
            task_id=task_id,
            stage_id=stage_id,
            reviewer_id=reviewer_id,
            audit_trail=[audit_entry],
            decided_at=decided_at,
        )

        async with session_factory() as session, session.begin():
            await SqliteExternalReviewGateRepository(session).save(gate)

        persisted = await _read_persisted_audit_comment(session_factory, gate.id)
        assert persisted == plain_comment, (
            f"[FAIL] plain audit comment was modified.\n"
            f"Expected: {plain_comment!r}\nGot: {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-ERGR-020-masking-3columns: 3 columns simultaneous masking
# ---------------------------------------------------------------------------
class TestThreeColumnSimultaneousMasking:
    """TC-IT-ERGR-020-masking-3columns: All 3 MaskedText columns redacted in one save."""

    async def test_three_masked_text_columns_redacted_simultaneously(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """Discord + Slack + GitHub all redacted across 3 separate MaskedText columns."""
        task_id, stage_id, reviewer_id = seeded_gate_context

        # snapshot_body_markdown: Discord token
        body = f"# 設計書\nDiscord token={_DISCORD_TOKEN} for webhook"
        snapshot = make_deliverable(body_markdown=body)

        # feedback_text: Slack token
        feedback = f"レビュー拒否。Slack: {_SLACK_TOKEN}"

        # audit comment: GitHub PAT
        comment = f"却下理由: GitHub PAT {_GITHUB_TOKEN} が混入していた"
        decided_at = datetime.now(UTC)
        audit_entry = make_audit_entry(
            action=AuditAction.REJECTED,
            comment=comment,
            occurred_at=decided_at,
        )

        gate = make_rejected_gate(
            task_id=task_id,
            stage_id=stage_id,
            reviewer_id=reviewer_id,
            deliverable_snapshot=snapshot,
            feedback_text=feedback,
            audit_trail=[audit_entry],
            decided_at=decided_at,
        )

        async with session_factory() as session, session.begin():
            await SqliteExternalReviewGateRepository(session).save(gate)

        persisted_snapshot = await _read_persisted_snapshot_body(session_factory, gate.id)
        persisted_feedback = await _read_persisted_feedback_text(session_factory, gate.id)
        persisted_comment = await _read_persisted_audit_comment(session_factory, gate.id)

        # snapshot_body_markdown — Discord
        assert _DISCORD_SENTINEL in persisted_snapshot, (
            "[FAIL] snapshot_body_markdown missing Discord sentinel in 3-column test."
        )
        assert _DISCORD_TOKEN not in persisted_snapshot

        # feedback_text — Slack
        assert _SLACK_SENTINEL in persisted_feedback, (
            "[FAIL] feedback_text missing Slack sentinel in 3-column test."
        )
        assert _SLACK_TOKEN not in persisted_feedback

        # audit comment — GitHub
        assert _GITHUB_SENTINEL in persisted_comment, (
            "[FAIL] audit_entries.comment missing GitHub PAT sentinel in 3-column test."
        )
        assert _GITHUB_TOKEN not in persisted_comment
