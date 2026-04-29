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
    """TC-UT-WF-057 / 058 / 059 — JSON シリアライズと例外でトークンマスキング。"""

    def test_057_model_dump_json_mode_masks_token(self) -> None:
        """TC-UT-WF-057: model_dump(mode='json') はトークンを REDACTED に置換。"""
        channel = make_notify_channel()
        dumped = channel.model_dump(mode="json")
        assert "<REDACTED:DISCORD_WEBHOOK>" in dumped["target"]
        assert "SyntheticToken_-abcXYZ" not in dumped["target"]

    def test_057_model_dump_python_mode_preserves_token(self) -> None:
        """TC-UT-WF-057: model_dump(mode='python') はプロセス内使用のため raw target を保持。"""
        channel = make_notify_channel()
        dumped = channel.model_dump()
        assert dumped["target"] == DEFAULT_DISCORD_WEBHOOK

    def test_058_model_dump_json_workflow_scans_clean(self) -> None:
        """TC-UT-WF-058: workflow.model_dump_json() は平文トークンセグメントなし。"""
        wf_payload = build_v_model_payload()
        wf = Workflow.from_dict(wf_payload)
        json_text = wf.model_dump_json()
        # トークンセグメント "SyntheticToken_-abcXYZ" は JSON 出力に出現してはならない。
        assert "SyntheticToken_-abcXYZ" not in json_text
        assert "<REDACTED:DISCORD_WEBHOOK>" in json_text
        # サニティチェック: ダンプ JSON は整形式 JSON で解析可能。
        parsed = json.loads(json_text)
        assert parsed["name"] == "V モデル開発フロー"

    def test_059_exception_detail_does_not_leak_token(self) -> None:
        """TC-UT-WF-059: WorkflowInvariantViolation message/detail は Discord トークンをマスク。"""
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
        # ネスト detail 辞書にもマスキング適用を検証。
        nested = cast("dict[str, object]", exc.detail["nested"])
        assert "c" * 30 not in str(nested["u"])

    def test_mask_helper_is_idempotent(self) -> None:
        """mask_discord_webhook を 2 回適用すると同じ結果 (スモーク)。"""
        original = f"https://discord.com/api/webhooks/123/{'x' * 20}"
        once = mask_discord_webhook(original)
        twice = mask_discord_webhook(once)
        assert once == twice
