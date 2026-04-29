""":class:`Directive` のための Aggregate レベル不変条件ヘルパ。

各ヘルパは **モジュール レベルの純粋関数** であるため、テストから ``import``
して直接呼べる — Norman / Steve が agent の ``aggregate_validators.py`` と
room の ``aggregate_validators.py`` で承認したのと同じテスタビリティ パターン。

ヘルパ:

1. :func:`_validate_text_range` — ``1 ≤ NFC(text) ≤ 10000``。長さは ``strip``
   無しの **NFC 正規化済み** テキストに対して判定する。CEO ディレクティブは
   意味のある先頭／末尾空白や改行（複数段落のブリーフ）を含む可能性がある。
2. :func:`_validate_task_link_immutable` — 既に non-``None`` ``task_id`` を持つ
   Directive に対する ``link_task`` 呼び出しを Fail Fast する。コンストラクタ
   経路（リポジトリ水和で使用）は任意の ``TaskId | None`` を受理する。永続的な
   属性値は *遷移* ではないため。``link_task`` のみが遷移違反を監視する
   （Directive detailed-design §確定 C 参照）。

命名は agent / room の先例（``_validate_*``）に従う。
"""

from __future__ import annotations

from uuid import UUID

from bakufu.domain.exceptions import DirectiveInvariantViolation

# Confirmation B: text 長境界（NFC 正規化後で 1〜10000）。
MIN_TEXT_LENGTH: int = 1
MAX_TEXT_LENGTH: int = 10_000


def _validate_text_range(text: str) -> None:
    """``Directive.text`` は 1〜10000 文字でなければならない（MSG-DR-001）。

    長さは **NFC 正規化済み** 文字列に対して判定される（フィールド バリデータが
    本ヘルパ呼び出し前にパイプラインを走らせる）。``strip`` は適用しない —
    CEO ディレクティブは意味のある先頭／末尾空白や複数段落ブロックを含む可能性
    がある。
    """
    length = len(text)
    if not (MIN_TEXT_LENGTH <= length <= MAX_TEXT_LENGTH):
        raise DirectiveInvariantViolation(
            kind="text_range",
            message=(
                f"[FAIL] Directive text must be "
                f"{MIN_TEXT_LENGTH}-{MAX_TEXT_LENGTH} characters (got {length})\n"
                f"Next: Trim directive content to <={MAX_TEXT_LENGTH} "
                f"NFC-normalized characters; for richer prompts use "
                f"multiple directives or attach a deliverable."
            ),
            detail={"length": length},
        )


def _validate_task_link_immutable(
    *,
    directive_id: UUID,
    existing_task_id: UUID | None,
    attempted_task_id: UUID,
) -> None:
    """既にリンク済みの Directive に対する ``link_task`` 呼び出しを拒否する。

    Confirmation C / D / Norman 凍結: 1 つの Directive が 1 つの Task に対応する
    のは設計上の前提。2 回目の ``link_task`` 呼び出しは新 TaskId が既存と等しい
    かに関わらず **常に** Fail Fast し、no-op にはしない。シンプルなコントラクト
    は Aggregate バリデータの特例を避け、ビジネス ルール「ディレクティブの再発行
    とは *新しい* Directive の作成を意味する」と一致する。

    Raises:
        DirectiveInvariantViolation: ``existing_task_id is not None`` の場合に
            ``kind='task_already_linked'``（MSG-DR-002）。
    """
    if existing_task_id is None:
        return
    raise DirectiveInvariantViolation(
        kind="task_already_linked",
        message=(
            f"[FAIL] Directive already has a linked Task: "
            f"directive_id={directive_id}, "
            f"existing_task_id={existing_task_id}\n"
            f"Next: Issue a new Directive instead of re-linking; one "
            f"Directive maps to one Task by design."
        ),
        detail={
            "directive_id": str(directive_id),
            "existing_task_id": str(existing_task_id),
            "attempted_task_id": str(attempted_task_id),
        },
    )


__all__ = [
    "MAX_TEXT_LENGTH",
    "MIN_TEXT_LENGTH",
    "_validate_task_link_immutable",
    "_validate_text_range",
]
