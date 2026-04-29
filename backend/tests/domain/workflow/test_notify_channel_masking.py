"""NotifyChannel シークレット マスキング (Confirmation G "target のシークレット扱い")。

TC-UT-WF-057 / 058 / 059 をカバー。トークン削除は設計書が
ドメイン層に pin する 3 つのシリアライゼーションパスに
適用する必須:

* ``model_dump(mode='json')`` は field_serializer 経由
* ``Workflow.model_dump_json()`` は同じ serializer にロール・アップ
* Exception ``message`` / ``detail`` は ``WorkflowInvariantViolation`` init 経由

永続化側マスキング (Outbox / audit_log / Conversation / 構造化ログ)
は設計に従い ``feature/persistence`` 責任でスコープ外。
"""

from __future__ import annotations

import json
from typing import cast

from bakufu.domain.exceptions import WorkflowInvariantViolation
from bakufu.domain.value_objects import mask_discord_webhook
from bakufu.domain.workflow import Workflow

from tests.factories.workflow import (
    DEFAULT_DISCORD_WEBHOOK,
    build_v_model_payload,
    make_notify_channel,
)


class TestNotifyChannelMasking:
    """TC-UT-WF-057 / 058 / 059 — token masked on JSON serialization & exceptions."""

    def test_057_model_dump_json_mode_masks_token(self) -> None:
        """TC-UT-WF-057: model_dump(mode='json') replaces token with REDACTED."""
        channel = make_notify_channel()
        dumped = channel.model_dump(mode="json")
        assert "<REDACTED:DISCORD_WEBHOOK>" in dumped["target"]
        assert "SyntheticToken_-abcXYZ" not in dumped["target"]

    def test_057_model_dump_python_mode_preserves_token(self) -> None:
        """TC-UT-WF-057: model_dump(mode='python') keeps raw target for in-process use."""
        channel = make_notify_channel()
        dumped = channel.model_dump()
        assert dumped["target"] == DEFAULT_DISCORD_WEBHOOK

    def test_058_model_dump_json_workflow_scans_clean(self) -> None:
        """TC-UT-WF-058: workflow.model_dump_json() shows no plaintext token segment."""
        wf_payload = build_v_model_payload()
        wf = Workflow.from_dict(wf_payload)
        json_text = wf.model_dump_json()
        # Token segment "SyntheticToken_-abcXYZ" must not appear in JSON output.
        assert "SyntheticToken_-abcXYZ" not in json_text
        assert "<REDACTED:DISCORD_WEBHOOK>" in json_text
        # Sanity check: the dumped JSON parses back as well-formed JSON.
        parsed = json.loads(json_text)
        assert parsed["name"] == "V モデル開発フロー"

    def test_059_exception_detail_does_not_leak_token(self) -> None:
        """TC-UT-WF-059: WorkflowInvariantViolation message/detail mask Discord tokens."""
        fake_message = (
            f"[FAIL] something happened with https://discord.com/api/webhooks/123/{'a' * 30}"
        )
        exc = WorkflowInvariantViolation(
            kind="from_dict_invalid",
            message=fake_message,
            detail={
                "url": f"https://discord.com/api/webhooks/123/{'b' * 30}",
                "nested": {"u": f"https://discord.com/api/webhooks/123/{'c' * 30}"},
            },
        )
        assert "a" * 30 not in exc.message
        # Verify masking applied to nested detail dict too.
        nested = cast("dict[str, object]", exc.detail["nested"])
        assert "c" * 30 not in str(nested["u"])

    def test_mask_helper_is_idempotent(self) -> None:
        """Applying mask_discord_webhook twice yields the same result (smoke)."""
        original = f"https://discord.com/api/webhooks/123/{'x' * 20}"
        once = mask_discord_webhook(original)
        twice = mask_discord_webhook(once)
        assert once == twice
