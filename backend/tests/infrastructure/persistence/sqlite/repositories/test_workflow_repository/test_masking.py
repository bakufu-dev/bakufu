"""Workflow Repository: §確定 H — MaskedJSONEncoded wiring + irreversibility.

TC-IT-WFR-013 / 014 — the contract surface this PR makes physical:

* **TC-IT-WFR-013**: Saving a Workflow whose ``EXTERNAL_REVIEW`` Stage
  carries a real-shape Discord webhook URL persists the
  ``notify_channels_json`` column with the secret token replaced by
  ``<REDACTED:DISCORD_WEBHOOK>``. The original token MUST NOT appear
  anywhere in the on-disk JSON. Verified via raw-SQL ``SELECT`` (which
  bypasses ORM type decoders) so the bytes that hit the disk are the
  bytes we read.

* **TC-IT-WFR-014**: §不可逆性 — once persisted, ``find_by_id`` on the
  same Workflow raises ``pydantic.ValidationError`` because the masked
  URL fails the ``NotifyChannel`` G7 regex (``[A-Za-z0-9_\\-]+`` for
  the token segment; ``<REDACTED:DISCORD_WEBHOOK>`` contains ``<>:``
  which the regex rejects). This is the *design contract*: re-entry of
  the webhook URL must come from CEO operator input, not from
  round-trip recovery.

Per ``docs/features/workflow-repository/test-design.md``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from bakufu.domain.value_objects import NotifyChannel, StageKind
from bakufu.domain.workflow import Workflow
from bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository import (
    SqliteWorkflowRepository,
)
from sqlalchemy import text

from tests.factories.workflow import make_stage, make_transition, make_workflow

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# 実際の形状 (ただし合成) の Discord webhook URL。トークンセグメントは
# 意図的に特徴的なものを使用して、アサーションがマスク後
# ディスク上バイトがそれを持たないことを証明できるようにする。
_REAL_SHAPE_TOKEN = "JeffMaskingProbe_-9876543210xyzABCDEFGHIJ"
_REAL_SHAPE_WEBHOOK = "https://discord.com/api/webhooks/1234567890123456789/" + _REAL_SHAPE_TOKEN
_DISCORD_REDACT_SENTINEL = "<REDACTED:DISCORD_WEBHOOK>"


def _make_external_review_workflow(*, target_url: str) -> Workflow:
    """入口 Stage が ``EXTERNAL_REVIEW`` + 与えられた webhook の Workflow を構築。

    返される形状は bare な ``Workflow`` aggregate；テスト本体が
    それを保存 / 再取得してディスク上バイトに対してアサート。
    """
    notify_channel = NotifyChannel(
        kind="discord",
        target=target_url,
    )
    review_stage = make_stage(
        name="外部レビュー",
        kind=StageKind.EXTERNAL_REVIEW,
        notify_channels=[notify_channel],
    )
    work_stage = make_stage(name="次の作業")
    transition = make_transition(
        from_stage_id=review_stage.id,
        to_stage_id=work_stage.id,
    )
    return make_workflow(
        stages=[review_stage, work_stage],
        transitions=[transition],
        entry_stage_id=review_stage.id,
    )


# ---------------------------------------------------------------------------
# TC-IT-WFR-013: MaskedJSONEncoded wiring (Schneier 申し送り #6 物理確認)
# ---------------------------------------------------------------------------
class TestNotifyChannelsJsonMaskedOnDisk:
    """TC-IT-WFR-013: ``notify_channels_json`` は raw token ではなく ``<REDACTED:...>`` を持つ。"""

    async def test_discord_webhook_token_redacted_in_persisted_json(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-013: raw-SQL ``SELECT`` はマスク済み JSON を示し、secret token は表示しない。

        2 つのアサーション（ポジティブ優先）：

        1. redaction sentinel が現れる — masking gateway が実行されたことを証明。
           masking ステップをサイレントにドロップするバグは
           sentinel を **ドロップし** token を平文で残す。
        2. 元の token は JSON 文字列内のどこにも現れない —
           認証情報はディスク上にどのような形式でも格納されない。
        """
        workflow = _make_external_review_workflow(target_url=_REAL_SHAPE_WEBHOOK)
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow)

        # Raw SQL — MaskedJSONEncoded.process_result_value を迂回して
        # ディスク上の文字通りのバイトを見る。
        async with session_factory() as session:
            stmt = text(
                "SELECT notify_channels_json FROM workflow_stages "
                "WHERE workflow_id = :workflow_id "
                "AND kind = 'EXTERNAL_REVIEW'"
            )
            row = (await session.execute(stmt, {"workflow_id": workflow.id.hex})).first()

        assert row is not None
        persisted_json = row[0]
        assert isinstance(persisted_json, str)

        # ポジティブ: redaction sentinel が存在する。
        assert _DISCORD_REDACT_SENTINEL in persisted_json, (
            f"[FAIL] notify_channels_json が redaction sentinel がない。\n"
            f"Next: workflow_stages.notify_channels_json カラム型が "
            f"MaskedJSONEncoded であることを確認； これは §確定 H 物理保証。 "
            f"Persisted JSON: {persisted_json!r}"
        )
        # ネガティブ: raw token は不在。
        assert _REAL_SHAPE_TOKEN not in persisted_json, (
            f"[FAIL] raw Discord webhook token が notify_channels_json に漏洩。\n"
            f"Next: これは §確定 H + Schneier 申し送り #6 "
            f"3 層防御が防止するように設計された壊滅的なケース。"
            f"NotifyChannel.field_serializer (Layer 1) AND MaskedJSONEncoded "
            f"(Layer 2 / TypeDecorator) 両方がまだ配置されていることを確認。 "
            f"Persisted JSON: {persisted_json!r}"
        )

    async def test_empty_notify_channels_persists_as_empty_array(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-013 補強: notify_channels のない Stage も問題なく永続化。

        ``WORK`` stages はデフォルトで notify_channels を持たない。
        カラムは NOT NULL で server_default は ``'[]'`` ；
        Repository の ``_to_row`` は ``[]`` (空リスト) を発行し、
        ``MaskedJSONEncoded.process_bind_param`` は
        これを ``"[]"`` JSON に正規化。このパスではマスキングアーティファクトなし。
        """
        workflow = make_workflow()  # 1 WORK stage, empty notify_channels
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow)

        async with session_factory() as session:
            stmt = text(
                "SELECT notify_channels_json FROM workflow_stages WHERE workflow_id = :workflow_id"
            )
            row = (await session.execute(stmt, {"workflow_id": workflow.id.hex})).first()

        assert row is not None
        # ``"[]"`` (明示的な空リスト JSON) または
        # JSON-valid な空コンテナ — 契約は「漏洩なし」であり「正確なバイト形式」ではない。
        # 両方の解釈が安全であることをアサート。
        assert _DISCORD_REDACT_SENTINEL not in str(row[0])
        # 文字列型 JSON 値を取得したことの簡易チェック。
        assert str(row[0]).strip() in ("[]", "null", "")


# ---------------------------------------------------------------------------
# TC-IT-WFR-014: §確定 H §不可逆性 — find_by_id returns Workflow with masked target
# ---------------------------------------------------------------------------
class TestFindByIdReturnsMaskedNotifyChannels:
    """TC-IT-WFR-014: マスク済み Workflow の ``find_by_id`` はマスク済み URL を返す。

    §確定 H §不可逆性 契約 (BUG-AT-002 後): notify_channels がディスク上でマスク
    されると、再構築された Workflow aggregate の ``target`` フィールドは redaction
    sentinel ``<REDACTED:DISCORD_WEBHOOK>`` を含む。原トークンの回復は不可能。

    G7 regex は redaction sentinel を許容するよう拡張されているため
    ``NotifyChannel.model_validate`` は成功する。不可逆性の保証は
    ``workflow_service.update()`` 側の明示的マスク検出 (WorkflowIrreversibleError)
    に移管された (BUG-AT-002 commit message 参照)。
    """

    async def test_find_by_id_returns_masked_target(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-014: save 後の find_by_id は masked URL を含む Workflow を返す。

        契約 (BUG-AT-002 後):

        * ``save`` は成功 (gateway は well-formed JSON を生成、token は redact済み)。
        * ``find_by_id`` は成功 — 再構築された Workflow の EXTERNAL_REVIEW Stage の
          notify_channels[0].target は redaction sentinel を含む。
        * 原トークンは Workflow aggregate のどこにも現れない (不可逆性の物理保証)。
        """
        workflow = _make_external_review_workflow(target_url=_REAL_SHAPE_WEBHOOK)
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow)

        async with session_factory() as session:
            reloaded = await SqliteWorkflowRepository(session).find_by_id(workflow.id)

        assert reloaded is not None
        review_stage = next(
            (s for s in reloaded.stages if s.kind == StageKind.EXTERNAL_REVIEW),
            None,
        )
        assert review_stage is not None
        assert len(review_stage.notify_channels) == 1
        masked_target = review_stage.notify_channels[0].target
        assert _DISCORD_REDACT_SENTINEL in masked_target, (
            f"[FAIL] reconstructed target に redaction sentinel が無い: {masked_target!r}"
        )
        assert _REAL_SHAPE_TOKEN not in masked_target, (
            f"[FAIL] 原トークンが reconstructed target に漏洩: {masked_target!r}"
        )
