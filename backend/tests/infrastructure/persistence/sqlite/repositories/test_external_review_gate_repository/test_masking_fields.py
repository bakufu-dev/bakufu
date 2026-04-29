"""ExternalReviewGate Repository: 3 カラムへの MaskedText 配線 (TC-IT-ERGR-020-masking-*).

RQ-ERGR-006 / §確定 R1-E ── 3 つの MaskedText カラムの物理検証:
  * external_review_gates.snapshot_body_markdown
  * external_review_gates.feedback_text
  * external_review_audit_entries.comment

各カラムは **raw SQL SELECT** で検証する ──
``MaskedText.process_result_value`` を迂回し、ディスク上の実バイトを確認するため。

テストケース 9 件:
  snapshot_body_markdown: masked / plain / roundtrip (3 件)
  feedback_text: masked / plain / roundtrip (3 件)
  comment: masked / plain (2 件)
  3 カラム同時: 1 件

``docs/features/external-review-gate-repository/test-design.md``
TC-IT-ERGR-020-masking-* 準拠。
Issue #36 ── M2 0008。
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
# secret トークン定数 (push-protection 回避のため実形を分割構築)
# ---------------------------------------------------------------------------

# Discord Bot Token ── [MN][A-Za-z\d]{23,}\.[\w-]{6}\.[\w-]{27,}
_DISCORD_TOKEN = "MTk4NjIyNDgz" + "NDcxOTI1MjQ4.ClFDg_." + "A" * 27
_DISCORD_SENTINEL = "<REDACTED:DISCORD_TOKEN>"

# GitHub PAT ── (?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}
_GITHUB_TOKEN = "ghp_" + "X" * 40
_GITHUB_SENTINEL = "<REDACTED:GITHUB_PAT>"

# Slack Bot Token ── xoxb-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24}
_SLACK_TOKEN = "xoxb-" + "1" * 11 + "-" + "2" * 11 + "-" + "A" * 24
_SLACK_SENTINEL = "<REDACTED:SLACK_TOKEN>"


# ---------------------------------------------------------------------------
# Raw-SQL ヘルパ (TypeDecorator.process_result_value を迂回)
# ---------------------------------------------------------------------------
async def _read_persisted_snapshot_body(
    session_factory: async_sessionmaker[AsyncSession],
    gate_id: UUID,
) -> str:
    """external_review_gates.snapshot_body_markdown の実バイトを取得する。"""
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
    """external_review_gates.feedback_text の実バイトを取得する。"""
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
    """external_review_audit_entries.comment の実バイトを取得する (最初のエントリ)。"""
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
    """TC-IT-ERGR-020-masking-snapshot-masked: snapshot_body_markdown
    の Discord トークンが redact される。"""

    async def test_discord_token_in_snapshot_body_redacted_on_disk(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """Raw-SQL SELECT が <REDACTED:DISCORD_TOKEN> を返し、生トークンはディスク上に残らない。"""
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
            "[FAIL] snapshot_body_markdown に Discord sentinel が"
            f"含まれない。\nPersisted: {persisted!r}"
        )
        assert _DISCORD_TOKEN not in persisted, (
            f"[FAIL] 生 Discord トークンが snapshot_body_markdown に漏洩した。\n"
            f"§確定 R1-E §不可逆性 違反。Persisted: {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-ERGR-020-masking-snapshot-plain
# ---------------------------------------------------------------------------
class TestSnapshotBodyMarkdownPlainPassthrough:
    """TC-IT-ERGR-020-masking-snapshot-plain: 平文は変更なしで保存される。"""

    async def test_plain_snapshot_body_is_passthrough(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """secret を含まない snapshot_body_markdown はバイト等価で保存される。"""
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
            f"[FAIL] 平文 snapshot_body_markdown が変更されている。\n"
            f"Expected: {plain_body!r}\nGot: {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-ERGR-020-masking-snapshot-roundtrip
# ---------------------------------------------------------------------------
class TestSnapshotBodyMarkdownRoundtripIrreversible:
    """TC-IT-ERGR-020-masking-snapshot-roundtrip: find_by_id はマスク済み body を返す。"""

    async def test_find_by_id_returns_masked_snapshot_body(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """snapshot_body_markdown に生 Discord トークンを保存 →
        find_by_id → body がマスクされている。"""
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
            f"[FAIL] find_by_id がマスクされていない snapshot_body_markdown を返した。\n"
            f"Restored: {restored_body!r}"
        )
        assert _DISCORD_TOKEN not in restored_body, (
            f"[FAIL] §確定 R1-E §不可逆性 違反: 生 Discord トークンが復元された。\n"
            f"Restored: {restored_body!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-ERGR-020-masking-feedback-masked
# -------------------------------------------------------------------
class TestFeedbackTextSlackTokenMasked:
    """TC-IT-ERGR-020-masking-feedback-masked: feedback_text
    中の Slack トークンが redact される。"""

    async def test_slack_token_in_feedback_text_redacted_on_disk(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """Raw-SQL SELECT が <REDACTED:SLACK_TOKEN> を返し、生トークンはディスク上に残らない。"""
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
            f"[FAIL] feedback_text に Slack sentinel が含まれない。\nPersisted: {persisted!r}"
        )
        assert _SLACK_TOKEN not in persisted, (
            f"[FAIL] 生 Slack トークンが feedback_text に漏洩した。\n"
            f"§確定 R1-E (§設計決定 ERGR-002) 違反。Persisted: {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-ERGR-020-masking-feedback-plain
# ---------------------------------------------------------------------------
class TestFeedbackTextPlainPassthrough:
    """TC-IT-ERGR-020-masking-feedback-plain: 平文 feedback は変更なしで保存される。"""

    async def test_plain_feedback_text_is_passthrough(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """secret を含まない feedback_text はバイト等価で保存される。"""
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
            f"[FAIL] 平文 feedback_text が変更されている。\n"
            f"Expected: {plain_feedback!r}\nGot: {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-ERGR-020-masking-feedback-roundtrip
# ---------------------------------------------------------------------------
class TestFeedbackTextRoundtripIrreversible:
    """TC-IT-ERGR-020-masking-feedback-roundtrip: find_by_id はマスク済み feedback を返す。"""

    async def test_find_by_id_returns_masked_feedback_text(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """feedback_text に Slack トークンを保存 → find_by_id →
        feedback_text がマスクされている。"""
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
            f"[FAIL] find_by_id がマスクされていない feedback_text を返した。\n"
            f"Restored: {restored.feedback_text!r}"
        )
        assert _SLACK_TOKEN not in restored.feedback_text, (
            f"[FAIL] §確定 R1-E §不可逆性 違反: 生 Slack トークンが復元された。\n"
            f"Restored: {restored.feedback_text!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-ERGR-020-masking-comment-masked
# ---------------------------------------------------------------------------
class TestAuditCommentGithubPatMasked:
    """TC-IT-ERGR-020-masking-comment-masked: 監査コメント中の GitHub PAT が redact される。"""

    async def test_github_pat_in_audit_comment_redacted_on_disk(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """Raw-SQL SELECT が <REDACTED:GITHUB_PAT> を返し、生 PAT はディスク上に残らない。"""
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
            f"[FAIL] 監査コメントに GitHub PAT sentinel が含まれない。\nPersisted: {persisted!r}"
        )
        assert _GITHUB_TOKEN not in persisted, (
            f"[FAIL] 生 GitHub PAT が audit_entries.comment に漏洩した。\n"
            f"§確定 R1-E 違反。Persisted: {persisted!r}"
        )


# ---------------------------------------------------------------------------
# TC-IT-ERGR-020-masking-comment-plain
# ---------------------------------------------------------------------------
class TestAuditCommentPlainPassthrough:
    """TC-IT-ERGR-020-masking-comment-plain: 平文コメントは変更なしで保存される。"""

    async def test_plain_audit_comment_is_passthrough(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """secret を含まない audit_entries.comment はバイト等価で保存される。"""
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
            f"[FAIL] 平文監査コメントが変更されている。\n"
            f"Expected: {plain_comment!r}\nGot: {persisted!r}"
        )


# -------------------------------------------------------------------
# TC-IT-ERGR-020-masking-3columns: 3 カラム同時 masking
# -------------------------------------------------------------------
class TestThreeColumnSimultaneousMasking:
    """TC-IT-ERGR-020-masking-3columns: 1 回の save で
    3 つの MaskedText カラム全てが redact される。"""

    async def test_three_masked_text_columns_redacted_simultaneously(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_gate_context: tuple[UUID, UUID, UUID],
    ) -> None:
        """別個の 3 つの MaskedText カラム全てで
        Discord + Slack + GitHub がいずれも redact される。"""
        task_id, stage_id, reviewer_id = seeded_gate_context

        # snapshot_body_markdown: Discord トークン
        body = f"# 設計書\nDiscord token={_DISCORD_TOKEN} for webhook"
        snapshot = make_deliverable(body_markdown=body)

        # feedback_text: Slack トークン
        feedback = f"レビュー拒否。Slack: {_SLACK_TOKEN}"

        # 監査コメント: GitHub PAT
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

        # snapshot_body_markdown ── Discord
        assert _DISCORD_SENTINEL in persisted_snapshot, (
            "[FAIL] snapshot_body_markdown missing Discord sentinel in 3-column test."
        )
        assert _DISCORD_TOKEN not in persisted_snapshot

        # feedback_text ── Slack
        assert _SLACK_SENTINEL in persisted_feedback, (
            "[FAIL] feedback_text missing Slack sentinel in 3-column test."
        )
        assert _SLACK_TOKEN not in persisted_feedback

        # 監査コメント ── GitHub
        assert _GITHUB_SENTINEL in persisted_comment, (
            "[FAIL] audit_entries.comment missing GitHub PAT sentinel in 3-column test."
        )
        assert _GITHUB_TOKEN not in persisted_comment
