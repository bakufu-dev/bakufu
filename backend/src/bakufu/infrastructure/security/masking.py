"""Fail-Secure フォールバック付きマスキング ゲートウェイ（§確定 A + §確定 F）。

レイヤード伏字化（順序は **固定**、Confirmation A 参照）:

1. **環境変数値** — 既知のシークレット環境変数を ``<REDACTED:ENV:{NAME}>``
   へ置換する。
2. **正規表現パターン** — 9 種類の代表的シークレット文字列形式
   （Anthropic / OpenAI / GitHub PAT / GitHub fine-grained PAT / AWS
   access key / AWS secret / Slack token / Discord bot token / Bearer
   token）。
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

``Bootstrap`` は起動時に :func:`init` を 1 度呼び出して本モジュールを
初期化する。以降の ``mask`` / ``mask_in`` 呼び出しはモジュールレベルの
状態を参照する。
"""

from __future__ import annotations

import logging
import os
import re
import sys
from typing import Final, cast

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

# Confirmation A: 9 つの正規表現パターン（順序は重要）。OpenAI パターンが
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
    # Bearer トークン（HTTP Authorization ヘッダ）。可読性のため
    # `Authorization: Bearer ` プレフィックスを残し、トークン部のみを
    # 伏字化する。
    (
        re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[A-Za-z0-9._\-]+"),
        r"\1<REDACTED:BEARER>",
    ),
]

# `init` で設定されるモジュールレベル状態。
_env_patterns: list[tuple[str, re.Pattern[str]]] = []
_home_pattern: re.Pattern[str] | None = None
_initialized: bool = False


def init() -> None:
    """環境変数パターン + ホームパスをコンパイルする。Bootstrap から 1 度だけ呼ぶ。

    冪等性: 後続呼び出しは環境変数パターンを再ロードする。これによりテスト
    セットアップは新しい環境変数値で前後をブラケットしつつ、モジュール
    内部に手を入れる必要がなくなる。

    Raises:
        BakufuConfigError: 環境変数スナップショット取得失敗時
            （Fail-Fast、MSG-PF-008）。:func:`load_env_patterns` から
            そのまま再送出される。
    """
    global _env_patterns, _home_pattern, _initialized
    _env_patterns = load_env_patterns()
    home = os.environ.get("HOME")
    _home_pattern = re.compile(re.escape(home)) if home else None
    _initialized = True


def mask(value: object) -> str:
    """``value`` から既知のシークレットを伏字化する。例外は送出しない（§確定 F）。

    引数型を ``object``（``str`` 限定ではない）にするのは、Fail-Secure
    リスナの外側 catch が任意のペイロードを型検証なくゲートウェイへ
    流せるようにするためである。内部失敗は捕捉され、文字列 *全体* が
    :data:`REDACT_MASK_ERROR` に置換される。これにより部分的な未伏字化
    漏洩を不可能にする。運用者が調査できるよう WARN ログを残す。
    """
    if not isinstance(value, str):
        # 防御的処理: 呼び出し側は文字列を渡す前提だが、リスナの外側
        # catch が異質なペイロードを通過させる可能性がある。Fail-Secure
        # の方針として文字列化してから処理を継続する。
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
        # レイヤ 1: 最も特定性の高い環境変数値を最優先で適用。
        for env_name, pattern in _env_patterns:
            out = pattern.sub(f"<REDACTED:ENV:{env_name}>", out)
        # レイヤ 2: 正規表現パターン（Anthropic を OpenAI より先に）。
        for pattern, replacement in _REGEX_PATTERNS:
            out = pattern.sub(replacement, out)
        # レイヤ 3: ホームパス。
        if _home_pattern is not None:
            out = _home_pattern.sub("<HOME>", out)
        return out
    except Exception as exc:  # pragma: no cover — defensive fallback
        logger.warning(
            "[WARN] Masking gateway fallback applied: kind=mask_error (%r)",
            exc,
        )
        return REDACT_MASK_ERROR


def mask_in(value: object) -> object:
    """``value`` を再帰的に走査し、すべての文字列に :func:`mask` を適用する。

    対応する型: ``str`` / ``list`` / ``tuple`` / ``dict``、およびスカラ
    （``int`` / ``float`` / ``bool`` / ``None``）。それ以外のオブジェクト
    は ``str()`` で文字列化してからマスクする。

    Confirmation F のオーバーフローガード: 構造体が大きすぎて走査時に
    :data:`MAX_BYTES_FOR_RECURSION` を超える（``sys.getsizeof`` 概算）
    場合、構造体 *全体* を :data:`REDACT_MASK_OVERFLOW` で置換する。
    """
    try:
        if sys.getsizeof(value) > MAX_BYTES_FOR_RECURSION:
            logger.warning(
                "[WARN] Masking gateway fallback applied: kind=mask_overflow "
                "(payload exceeds %d bytes)",
                MAX_BYTES_FOR_RECURSION,
            )
            return REDACT_MASK_OVERFLOW
    except (TypeError, OSError):  # pragma: no cover — defensive
        # 一部のカスタムオブジェクトは getsizeof を正しく実装しない。
        # その場合は小さいものとみなして処理を続行する。
        pass

    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        return mask(value)
    if isinstance(value, list):
        items_list = cast("list[object]", value)
        return [mask_in(item) for item in items_list]
    if isinstance(value, tuple):
        items_tuple = cast("tuple[object, ...]", value)
        return tuple(mask_in(item) for item in items_tuple)
    if isinstance(value, dict):
        items_dict = cast("dict[object, object]", value)
        return {key: mask_in(val) for key, val in items_dict.items()}
    # フォールバック: 未知型は文字列化してマスクを適用する。これは
    # §確定 F の「datetime / bytes」経路に該当する。
    try:
        return mask(str(value))
    except Exception:
        logger.warning(
            "[WARN] Masking gateway fallback applied: kind=mask_error (stringification failed)"
        )
        return REDACT_MASK_ERROR


def is_initialized() -> bool:
    """:func:`init` 呼び出し済みなら ``True``。

    リスナ側はこれを参照することで、:func:`init` を呼び忘れた
    テストセットアップで生値がテスト DB に漏洩する事態を未然に
    短絡できる。
    """
    return _initialized


__all__ = [
    "MAX_BYTES_FOR_RECURSION",
    "REDACT_LISTENER_ERROR",
    "REDACT_MASK_ERROR",
    "REDACT_MASK_OVERFLOW",
    "init",
    "is_initialized",
    "mask",
    "mask_in",
]
