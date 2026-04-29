"""Fail-Secure フォールバック付きマスキング ゲートウェイ（§確定 A + §確定 F）。

レイヤード伏字化（順序は **固定**、Confirmation A 参照）:

1. **環境変数値** — 既知のシークレット環境変数を ``<REDACTED:ENV:{NAME}>``
   へ置換する。
2. **正規表現パターン** — 10 種類の代表的シークレット文字列形式
   （Anthropic / OpenAI / GitHub PAT / GitHub fine-grained PAT / AWS
   access key / AWS secret / Slack token / Discord bot token / Bearer
   token / Discord webhook URL）。
3. **ホームパス** — 実行ユーザの ``$HOME`` 絶対パスを ``<HOME>`` に
   置換し、ログ出力で FS レイアウトを漏らさないようにする。

Fail-Secure 契約（§確定 F）
---------------------------
``mask`` および ``mask_in`` は **絶対に例外を送出しない**。内部失敗は
すべて捕捉され、対象ペイロードはセンチネル
（``<REDACTED:MASK_ERROR>`` / ``<REDACTED:MASK_OVERFLOW>`` /
``<REDACTED:LISTENER_ERROR>``）に置換される。生の値が下流へ伝播する
ことは **決して** 許さない。シークレット漏洩を起こすくらいなら運用継続
を犠牲にする方針である。

``Bootstrap`` は起動時に ``MaskingGateway.init`` を 1 度呼び出して本モジュールを
初期化する。以降の呼び出しも ``MaskingGateway`` の classmethod を明示的に使う。
"""

from __future__ import annotations

import logging
import os
import re
import sys
from typing import ClassVar, Final, cast

from bakufu.infrastructure.security.masked_env import load_env_patterns

logger = logging.getLogger(__name__)

# §確定 F の Fail-Secure 置換用センチネル定数。
REDACT_MASK_ERROR: Final = "<REDACTED:MASK_ERROR>"
REDACT_MASK_OVERFLOW: Final = "<REDACTED:MASK_OVERFLOW>"
REDACT_LISTENER_ERROR: Final = "<REDACTED:LISTENER_ERROR>"

# Confirmation F: dict / list の走査に上限を設け、誤って 10 MB 級の
# ペイロードを渡された際にマスカが暴走しないようにする。これを超える
# 場合は構造ごと一括置換する。
MAX_BYTES_FOR_RECURSION: Final = 1_048_576  # 1 MiB

# Confirmation A: 10 個の正規表現パターン（順序は重要）。OpenAI パターンが
# `sk-ant-...` プレフィックスにも一致してしまうため、Anthropic を先に
# 適用する。優先順位を読者に分かりやすくするため、明示的な Anthropic
# パターンを先頭に置く。
_REGEX_PATTERNS: Final[list[tuple[re.Pattern[str], str]]] = [
    (
        re.compile(r"sk-ant-(?:api03-)?[A-Za-z0-9_\-]{40,}"),
        "<REDACTED:ANTHROPIC_KEY>",
    ),
    # OpenAI の `sk-` プレフィックスは Anthropic と重複する。Anthropic
    # キーを OpenAI 用置換文字列で二重伏字化しないよう否定先読みを
    # 用いる。
    (
        re.compile(r"sk-(?!ant-)[A-Za-z0-9]{20,}"),
        "<REDACTED:OPENAI_KEY>",
    ),
    (
        re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}"),
        "<REDACTED:GITHUB_PAT>",
    ),
    (
        re.compile(r"github_pat_[A-Za-z0-9_]{82,}"),
        "<REDACTED:GITHUB_PAT>",
    ),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "<REDACTED:AWS_ACCESS_KEY>"),
    (
        re.compile(r"aws_secret_access_key\s*=\s*[A-Za-z0-9/+=]{40}"),
        "<REDACTED:AWS_SECRET>",
    ),
    (
        re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
        "<REDACTED:SLACK_TOKEN>",
    ),
    (
        re.compile(r"[MN][A-Za-z\d]{23,}\.[\w-]{6}\.[\w-]{27,}"),
        "<REDACTED:DISCORD_TOKEN>",
    ),
    (
        re.compile(r"https://discord\.com/api/webhooks/([0-9]{1,30})/([A-Za-z0-9_\-]{1,100})"),
        r"https://discord.com/api/webhooks/\1/<REDACTED:DISCORD_WEBHOOK>",
    ),
    # Bearer トークン（HTTP Authorization ヘッダ）。可読性のため
    # `Authorization: Bearer ` プレフィックスを残し、トークン部のみを
    # 伏字化する。
    (
        re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[A-Za-z0-9._\-]+"),
        r"\1<REDACTED:BEARER>",
    ),
]


class MaskingGateway:
    """Fail-Secure な伏字化ゲートウェイ。

    環境変数・正規表現・ホームパスの順序と内部状態をこのクラスへ閉じる。
    モジュール直下に公開 callable alias を置かず、入口を classmethod に一本化する。
    """

    _env_patterns: ClassVar[list[tuple[str, re.Pattern[str]]]] = []
    _home_pattern: ClassVar[re.Pattern[str] | None] = None
    _initialized: ClassVar[bool] = False

    @classmethod
    def init(cls) -> None:
        """環境変数パターン + ホームパスをコンパイルする。Bootstrap から 1 度だけ呼ぶ。"""
        cls._env_patterns = load_env_patterns()
        home = os.environ.get("HOME")
        cls._home_pattern = re.compile(re.escape(home)) if home else None
        cls._initialized = True

    @classmethod
    def mask(cls, value: object) -> str:
        """``value`` から既知のシークレットを伏字化する。例外は送出しない（§確定 F）。"""
        if not isinstance(value, str):
            try:
                value = str(value)
            except Exception:
                logger.warning(
                    "[WARN] Masking gateway fallback applied: kind=mask_error "
                    "(non-str input could not be coerced)"
                )
                return REDACT_MASK_ERROR
        try:
            out: str = value
            for env_name, pattern in cls._env_patterns:
                out = pattern.sub(f"<REDACTED:ENV:{env_name}>", out)
            for pattern, replacement in _REGEX_PATTERNS:
                out = pattern.sub(replacement, out)
            if cls._home_pattern is not None:
                out = cls._home_pattern.sub("<HOME>", out)
            return out
        except Exception as exc:  # pragma: no cover — defensive fallback
            logger.warning(
                "[WARN] Masking gateway fallback applied: kind=mask_error (%r)",
                exc,
            )
            return REDACT_MASK_ERROR

    @classmethod
    def mask_in(cls, value: object) -> object:
        """``value`` を再帰的に走査し、すべての文字列に ``mask`` を適用する。"""
        try:
            if sys.getsizeof(value) > MAX_BYTES_FOR_RECURSION:
                logger.warning(
                    "[WARN] Masking gateway fallback applied: kind=mask_overflow "
                    "(payload exceeds %d bytes)",
                    MAX_BYTES_FOR_RECURSION,
                )
                return REDACT_MASK_OVERFLOW
        except (TypeError, OSError):  # pragma: no cover — defensive
            pass

        if value is None or isinstance(value, bool | int | float):
            return value
        if isinstance(value, str):
            return cls.mask(value)
        if isinstance(value, list):
            items_list = cast("list[object]", value)
            return [cls.mask_in(item) for item in items_list]
        if isinstance(value, tuple):
            items_tuple = cast("tuple[object, ...]", value)
            return tuple(cls.mask_in(item) for item in items_tuple)
        if isinstance(value, dict):
            items_dict = cast("dict[object, object]", value)
            return {key: cls.mask_in(val) for key, val in items_dict.items()}
        try:
            return cls.mask(str(value))
        except Exception:
            logger.warning(
                "[WARN] Masking gateway fallback applied: kind=mask_error (stringification failed)"
            )
            return REDACT_MASK_ERROR

    @classmethod
    def is_initialized(cls) -> bool:
        """``init`` 呼び出し済みなら ``True``。"""
        return cls._initialized


__all__ = [
    "MAX_BYTES_FOR_RECURSION",
    "REDACT_LISTENER_ERROR",
    "REDACT_MASK_ERROR",
    "REDACT_MASK_OVERFLOW",
    "MaskingGateway",
]
