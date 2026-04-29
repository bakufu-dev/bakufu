"""InternalReviewGate 用に検証済みの GateRole 型エイリアス。

GateRole は、エージェントがどの論理レビュアー カテゴリに属するかを識別する
自由形式の slug ラベル（例 ``"security"``、``"lead-dev"``、``"qa-1"``）。
:class:`Role`（エージェント能力の固定 enum）とは **異なる** — GateRole は
Workflow Stage 構成の一部として Gate ごとに定義される。
"""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator

# ---------------------------------------------------------------------------
# GateRole 検証済み型エイリアス
# ---------------------------------------------------------------------------
_GATE_ROLE_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_GATE_ROLE_MAX_LEN: int = 40


def _validate_gate_role(value: str) -> str:
    """:data:`GateRole` の slug パターンを強制する。

    ルール（NFC 正規化後にすべてチェック）:

    * 1〜40 文字（コードポイント数）。
    * 小文字 ASCII 文字、数字、ハイフンのみ。
    * 小文字英字で開始しなければならない（数字始まりの slug は数値 ID と紛らわしい
      ので拒否）。
    * 連続ハイフン（``--``）禁止（long オプションのように見えてダウンストリーム
      ツールを混乱させるため）。
    * 先頭／末尾ハイフン禁止（正規表現アンカーがカバー）。
    """
    length = len(value)
    if not (1 <= length <= _GATE_ROLE_MAX_LEN):
        raise ValueError(
            f"GateRole must be 1-{_GATE_ROLE_MAX_LEN} characters (got length={length})"
        )
    if not _GATE_ROLE_RE.fullmatch(value):
        raise ValueError(
            f"GateRole must match the slug pattern "
            f"(lowercase letters/digits/hyphens, letter-initial, no consecutive hyphens); "
            f"got {value!r}"
        )
    return value


type GateRole = Annotated[str, AfterValidator(_validate_gate_role)]
""":class:`InternalReviewGate` におけるロールの検証済み slug 識別子。

GateRole は、エージェントがどの論理レビュアー カテゴリに属するかを識別する自由
形式の文字列ラベル（例 ``"security"``、``"lead-dev"``、``"qa-1"``）。:class:`Role`
（エージェント能力の固定 enum）とは **異なる** — GateRole は Workflow Stage 構成
の一部として Gate ごとに定義され、ワークフロー作成者が選ぶ任意の slug が可能。

検証ルール（:func:`_validate_gate_role` で強制）:

* 1〜40 NFC 正規化文字。
* 小文字 ASCII 文字、数字、ハイフンのみ。
* 小文字英字で開始しなければならない。
* 連続ハイフン（``--``）禁止。
* 末尾ハイフン禁止（正規表現アンカーがカバー）。
"""


__all__ = [
    "GateRole",
]
