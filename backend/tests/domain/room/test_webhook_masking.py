"""Discord Webhook シークレット マスキング (TC-UT-RM-014)。

Confirmation H: ``RoomInvariantViolation`` は
``message`` と ``detail`` の両方に含まれる webhook URL を
構築時にマスキング。``Room.name`` / ``Room.description`` /
``PromptKit.prefix_markdown`` はすべてユーザーペースト テキストを
含む可能性があり webhook URL を含む可能性がある。例外パスは
そのシークレットがログ行または HTTP レスポンス本体に
シリアライズされる前の**最後の**防御である。
"""

from __future__ import annotations

import pytest
from bakufu.domain.exceptions import RoomInvariantViolation

from tests.factories.room import make_room

# 説明長チェック (>500 文字) に失敗するよう設計された webhook URL。
# ID セグメント (数値) は表示; トークンセグメントはマスキング対象。
_WEBHOOK_ID = "1234567890123456789"
_WEBHOOK_TOKEN = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQRSTUVWX"
_WEBHOOK_URL = f"https://discord.com/api/webhooks/{_WEBHOOK_ID}/{_WEBHOOK_TOKEN}"
_REDACTED = "<REDACTED:DISCORD_WEBHOOK>"


class TestWebhookMaskingOnDescriptionViolation:
    """TC-UT-RM-014: 説明文内の webhook URL は例外テキストでマスキング。"""

    def test_token_segment_is_redacted_in_message(self) -> None:
        """TC-UT-RM-014: exception.message はマスキング済みトークンマーカーを含む。"""
        # >500 文字の説明文を構築、webhook URL を**含める**。
        description = _WEBHOOK_URL + ("a" * 600)
        with pytest.raises(RoomInvariantViolation) as excinfo:
            make_room(description=description)
        assert _WEBHOOK_TOKEN not in excinfo.value.message
        # 追跡可能性のために webhook ID は残す; トークンだけマスキング。

    def test_token_segment_does_not_leak_into_str_exc(self) -> None:
        """TC-UT-RM-014: str(exc) (デフォルトロギングで使用) はトークンを含まない。"""
        description = _WEBHOOK_URL + ("a" * 600)
        with pytest.raises(RoomInvariantViolation) as excinfo:
            make_room(description=description)
        assert _WEBHOOK_TOKEN not in str(excinfo.value)


class TestWebhookMaskingOnDetail:
    """TC-UT-RM-014: detail 辞書に埋め込まれた webhook URL もマスキング。"""

    def test_redacted_marker_substitutes_token_in_detail(self) -> None:
        """TC-UT-RM-014: 例外パスが生成する detail 値はマスキング。

        webhook URL を含む過大サイズ名で name_range 違反を起動。
        Aggregate バリデーター は ``detail`` に構造データのみ
        (長さ / カウント) を配置するが、マスキング パスは全辞書を
        走査するため、文字列値コンテキストは
        :func:`mask_discord_webhook_in` を通す。契約は detail 値が
        生のトークンセグメントを含まないこと。
        """
        # webhook URL を含む過大サイズ名 (>80 文字) を構築。
        name = _WEBHOOK_URL + "x"
        with pytest.raises(RoomInvariantViolation) as excinfo:
            make_room(name=name)
        # detail 内の全文字列値を走査; トークンを公開してはならない。
        for value in excinfo.value.detail.values():
            assert _WEBHOOK_TOKEN not in str(value)


class TestWebhookMaskingIdempotent:
    """Confirmation H 補足: マスキングを 2 回適用すると同じ文字列になる。"""

    def test_already_masked_url_is_not_re_substituted(self) -> None:
        """``mask_discord_webhook`` は冪等のため再適用は no-op。"""
        from bakufu.domain.value_objects import mask_discord_webhook

        once = mask_discord_webhook(_WEBHOOK_URL)
        twice = mask_discord_webhook(once)
        assert once == twice
        assert _REDACTED in once
