"""DirectiveInvariantViolation webhook auto-mask テスト (TC-UT-DR-007)。

Confirmation E: ``DirectiveInvariantViolation`` は
:class:`Exception` ``__init__`` **前に** ``message`` 上で
``mask_discord_webhook`` を、``detail`` 上で
``mask_discord_webhook_in`` を実行し、埋め込み webhook URL の
シークレット ``token`` セグメントがシリアライズ、ロギング、
HTTP エラーレスポンスを通してリークしない。CEO directives は
webhook URL を含む可能性があるユーザーペースト テキストを含められる;
Aggregate 境界はマスキング可能な最後のレイヤー (永続化前)。
"""

from __future__ import annotations

import pytest
from bakufu.domain.exceptions import DirectiveInvariantViolation

from tests.factories.directive import make_directive

# 有効形の Discord webhook URL。数値 ``id`` セグメントは
# 表示を保つ (監査追跡可能) トークンセグメントは
# ``<REDACTED:DISCORD_WEBHOOK>`` にマスキング必須。
_WEBHOOK_ID = "1234567890123456789"
_WEBHOOK_TOKEN = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQRSTUVWX"
_WEBHOOK_URL = f"https://discord.com/api/webhooks/{_WEBHOOK_ID}/{_WEBHOOK_TOKEN}"
_REDACTED = "<REDACTED:DISCORD_WEBHOOK>"


class TestWebhookMaskingOnTextRangeViolation:
    """TC-UT-DR-007: 過大テキスト内 webhook URL は例外テキストでマスキング。"""

    def test_token_does_not_appear_in_message(self) -> None:
        """TC-UT-DR-007: exception.message はマスキング済みマーカーのみを含む。"""
        # 10001 文字テキストを構築、webhook URL を **含める**。
        text = _WEBHOOK_URL + ("a" * 10_001)
        with pytest.raises(DirectiveInvariantViolation) as excinfo:
            make_directive(text=text)
        assert _WEBHOOK_TOKEN not in excinfo.value.message

    def test_token_does_not_leak_into_str_exc(self) -> None:
        """TC-UT-DR-007: str(exc) (デフォルトロギングパス) もマスキング。"""
        text = _WEBHOOK_URL + ("a" * 10_001)
        with pytest.raises(DirectiveInvariantViolation) as excinfo:
            make_directive(text=text)
        assert _WEBHOOK_TOKEN not in str(excinfo.value)


class TestWebhookMaskingOnDetail:
    """TC-UT-DR-007: detail 辞書値も再帰的にマスキング。"""

    def test_detail_values_carry_no_token(self) -> None:
        """TC-UT-DR-007: あらゆる str 値 detail アイテムは mask_discord_webhook_in を通る。"""
        text = _WEBHOOK_URL + ("a" * 10_001)
        with pytest.raises(DirectiveInvariantViolation) as excinfo:
            make_directive(text=text)
        for value in excinfo.value.detail.values():
            assert _WEBHOOK_TOKEN not in str(value)


class TestWebhookMaskingIdempotent:
    """Confirmation E 補足: マスキングは冪等。"""

    def test_re_application_does_not_double_substitute(self) -> None:
        """``mask_discord_webhook`` を 2 回適用すると同じ文字列を得る。"""
        from bakufu.domain.value_objects import mask_discord_webhook

        once = mask_discord_webhook(_WEBHOOK_URL)
        twice = mask_discord_webhook(once)
        assert once == twice
        assert _REDACTED in once
