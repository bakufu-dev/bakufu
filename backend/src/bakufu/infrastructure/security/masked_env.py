"""マスキング ゲートウェイのレイヤ 1: 既知の環境変数値の伏字化。

Bootstrap が起動時に固定アローリストに従って環境変数値を収集し、正規
表現置換テーブルへコンパイルする。本テーブルは ``mask()`` 呼び出し
ごとに参照され、合致したエントリは ``<REDACTED:ENV:{NAME}>`` で置換
される。

なぜアローリストか（vs.「全環境変数」を対象にしない理由）
----------------------------------------------------------
``PATH``、``HOME``、``LANG`` のように無害なデータを保持する環境変数も
存在する。それらまで含めると CLI 出力や監査テキストが過剰に伏字化され、
トラブルシューティングが困難になる。アローリストは
``docs/design/domain-model/storage.md`` で確定した一覧と同一だが、
1 点だけ置換している: MVP では SQLCipher を採用しないため
``BAKUFU_DB_KEY`` を除外し（``masking.md`` の Confirmation を参照）、
代わりに ``BAKUFU_DISCORD_BOT_TOKEN`` を追加する。Discord 通知系統は
脅威モデル §資産 でも高機密資産として位置づけられるためである。

文字数下限 8 文字
----------------
短い値（空文字や 4 文字程度のマーカ等）は事故的にあらゆる箇所と一致して
しまう。8 文字未満の値はスキップしつつ INFO ログを残し、運用者が
誤設定された環境変数に気付けるようにする。

Fail-Fast 契約（§確定 F）
-------------------------
``load_env_patterns`` は OS が ``os.environ`` アクセス自体を拒否したり、
値の正規表現コンパイルに失敗した場合に
:class:`bakufu.infrastructure.exceptions.BakufuConfigError` を
``msg_id='MSG-PF-008'`` で送出する。Bootstrap がこれを捕捉し非ゼロ
終了する。マスキング レイヤ 1 を無効化したまま起動すれば、システムの
他部分が依存する信頼境界を黙って弱化させてしまうためである。
"""

from __future__ import annotations

import logging
import os
import re

from bakufu.infrastructure.exceptions import BakufuConfigError

logger = logging.getLogger(__name__)

# ``docs/features/persistence-foundation/detailed-design/modules.md``
# §Module masked_env.py に従う固定アローリスト。変更は設計ドキュメントの
# PR を経由する。
KNOWN_ENV_KEYS: tuple[str, ...] = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GH_TOKEN",
    "GITHUB_TOKEN",
    "OAUTH_CLIENT_SECRET",
    "BAKUFU_DISCORD_BOT_TOKEN",
)

# この値より短い値はスキップする。誤マッチによる過剰伏字化を防止する。
MIN_ENV_VALUE_LENGTH: int = 8


def load_env_patterns() -> list[tuple[str, re.Pattern[str]]]:
    """既知環境変数の伏字化テーブルをコンパイルする。

    Returns:
        ``(env_name, compiled_pattern)`` タプルのリスト。現プロセスに
        該当環境変数が一つも設定されていなければ空リストを返す。CI や
        新しい開発環境では正当な状態であり、失敗ではなく INFO ログを
        出すに留める。

    Raises:
        BakufuConfigError: ``msg_id='MSG-PF-008'``。``os.environ``
            アクセス自体が例外を送出した場合や、いずれかの値が
            ``re.compile`` に失敗した場合。Bootstrap はここで
            非ゼロ終了する。レイヤ 1 を無効化した縮退運転は許容しない。
    """
    try:
        env_snapshot = dict(os.environ)
    except OSError as exc:
        # ``os.environ`` アクセスは特殊な OS 状態（chroot 不全、FS 破損
        # 等）で失敗し得る。マスキング レイヤ 1 は信頼境界の一部であり
        # オプションではないため、ここで Fail Fast する。
        raise BakufuConfigError(
            msg_id="MSG-PF-008",
            message=(
                f"[FAIL] Masking environment dictionary load failed: "
                f"{exc!r}\n"
                f"Next: Cannot start with partial masking layer. "
                f"Investigate env access permissions and OS-level "
                f"masking config; restart bakufu after fix."
            ),
        ) from exc

    patterns: list[tuple[str, re.Pattern[str]]] = []
    skipped_short: list[str] = []
    for env_name in KNOWN_ENV_KEYS:
        raw = env_snapshot.get(env_name)
        if raw is None:
            continue
        if len(raw) < MIN_ENV_VALUE_LENGTH:
            skipped_short.append(env_name)
            continue
        try:
            patterns.append((env_name, re.compile(re.escape(raw))))
        except re.error as exc:
            # ``re.escape`` は安全なパターンを生成するため理論上ここには
            # 到達しないが、信頼境界を維持するため Fail Fast する。
            raise BakufuConfigError(
                msg_id="MSG-PF-008",
                message=(
                    f"[FAIL] Masking environment dictionary load "
                    f"failed: regex compile error for {env_name}: "
                    f"{exc!r}\n"
                    f"Next: Cannot start with partial masking layer. "
                    f"Investigate env access permissions and OS-level "
                    f"masking config; restart bakufu after fix."
                ),
            ) from exc

    if not patterns:
        logger.info(
            "[INFO] Masking layer 1 (env): 0 patterns loaded "
            "(no known env vars set or all below length floor)."
        )
    if skipped_short:
        logger.info(
            "[INFO] Masking layer 1 (env): skipped %d env vars below length floor %d: %s",
            len(skipped_short),
            MIN_ENV_VALUE_LENGTH,
            ", ".join(sorted(skipped_short)),
        )
    return patterns


__all__ = [
    "KNOWN_ENV_KEYS",
    "MIN_ENV_VALUE_LENGTH",
    "load_env_patterns",
]
