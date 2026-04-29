"""bakufu ドメインの横断的ヘルパー関数および注釈付き文字列型。

すべての Aggregate（Empire / Workflow / Agent / ...）で共有される 2 つのヘルパ:

* :func:`nfc_strip` — 名前正規化パイプライン（NFC → strip → 長さ）。
  Empire detailed-design §Confirmation B と Workflow §Confirmation B を満たす。
* :func:`mask_discord_webhook` — Discord webhook URL のシークレット ``token``
  セグメントを ``<REDACTED:DISCORD_WEBHOOK>`` に置き換え、監査追跡用に ``id``
  セグメントを保持する。Workflow detailed-design §Confirmation G「target のシーク
  レット扱い」が要求する。
"""

from __future__ import annotations

import re
import unicodedata
from typing import Annotated, cast

from pydantic import BeforeValidator, Field

# ---------------------------------------------------------------------------
# 名前正規化（Confirmation B）
# ---------------------------------------------------------------------------


def nfc_strip(value: object) -> object:
    """detailed-design §Confirmation B に従い NFC 正規化と ``strip`` を適用する。

    パブリック関数として、兄弟 Aggregate（Empire / Workflow / Agent / ...）が正規化
    パイプラインの **単一** 実装を共有できるようにする。``str`` 入力に対してのみ
    動作し、非文字列値はそのまま通過させる。これにより、サイレントに型強制せず、
    Pydantic の下流型検証が標準のエラー形で報告できる。
    """
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value).strip()
    return value


# 同じパイプラインを採用する兄弟 VO / Aggregate が使用するパブリック エイリアス。
type NormalizedShortName = Annotated[
    str,
    BeforeValidator(nfc_strip),
    Field(min_length=1, max_length=80),
]
"""NFC+strip の BeforeValidator と 1〜80 文字 Field 境界が付与された ``str``。

:class:`RoomRef` および 80 文字 short-name コントラクトを採用する将来の VO で使用。
"""

type NormalizedAgentName = Annotated[
    str,
    BeforeValidator(nfc_strip),
    Field(min_length=1, max_length=40),
]
""":class:`AgentRef`（Agent.name 規定）用の 1〜40 文字バリエーション。"""


# ---------------------------------------------------------------------------
# Discord webhook シークレット マスキング（Workflow §Confirmation G）
# ---------------------------------------------------------------------------
# id（数値）を別キャプチャすることで、監査／ログ出力で id を可視のままにし、token
# セグメントだけを伏字化する。^ / $ を付けない緩いアンカーで、URL がより大きい
# 文字列（例外 detail dict、JSON ペイロード、ログ行）に埋め込まれていてもパターン
# にマッチする。
_DISCORD_WEBHOOK_PATTERN = re.compile(
    r"https://discord\.com/api/webhooks/([0-9]+)/([A-Za-z0-9_\-]+)"
)
_DISCORD_WEBHOOK_REDACTED_TOKEN = "<REDACTED:DISCORD_WEBHOOK>"


def mask_discord_webhook(text: str) -> str:
    """Discord webhook URL のシークレット ``token`` セグメントを全て置き換える。

    snowflake の ``id`` は追跡性のため保持する（audit_log が *どの* webhook が関与
    したかを特定できる）一方、認証セグメントを伏字化する。冪等: 2 回適用しても
    同じ結果になる。
    """
    return _DISCORD_WEBHOOK_PATTERN.sub(
        rf"https://discord.com/api/webhooks/\1/{_DISCORD_WEBHOOK_REDACTED_TOKEN}",
        text,
    )


def mask_discord_webhook_in(value: object) -> object:
    """値内の文字列に :func:`mask_discord_webhook` を再帰的に適用する。

    ``str`` / ``list`` / ``tuple`` / ``dict`` 構造を巡回するため、ネストされた診断
    ペイロード（例外の ``detail`` で使用）がリスト要素や dict 値を介してトークンを
    漏洩することを防ぐ。``cast`` 呼び出しは、bare ``isinstance`` ナローイングだけ
    では pyright strict が推論できない要素型情報を与える。
    """
    if isinstance(value, str):
        return mask_discord_webhook(value)
    if isinstance(value, list):
        items_list = cast("list[object]", value)
        return [mask_discord_webhook_in(item) for item in items_list]
    if isinstance(value, tuple):
        items_tuple = cast("tuple[object, ...]", value)
        return tuple(mask_discord_webhook_in(item) for item in items_tuple)
    if isinstance(value, dict):
        items_dict = cast("dict[object, object]", value)
        return {key: mask_discord_webhook_in(val) for key, val in items_dict.items()}
    return value


__all__ = [
    "NormalizedAgentName",
    "NormalizedShortName",
    "mask_discord_webhook",
    "mask_discord_webhook_in",
    "nfc_strip",
]
