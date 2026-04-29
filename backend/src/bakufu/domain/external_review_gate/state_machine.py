""":class:`ExternalReviewGate` Aggregate のための decision-table state machine。

``docs/features/external-review-gate/detailed-design.md`` §確定 B
（state machine テーブル ロック）と §確定 A（Method x current_decision の
ディスパッチ表）を実装する。コントラクトは意図的に
**フラットな ``Mapping[(ReviewDecision, str), ReviewDecision]``** であり、
``if-elif`` 階段ではない。理由:

1. 許可遷移の集合がきっちり 1 つの構造で列挙可能 — コードレビュー時に §確定 A の
   16 セル ディスパッチ表（4 メソッド × 4 状態）と一目で照合できる。
2. ルックアップ関数は未知の ``(decision, action)`` 対を ``KeyError`` で拒否する
   ため、呼び元は失敗を
   :class:`ExternalReviewGateInvariantViolation(kind='decision_already_decided')`
   で包む — もう PENDING ではない Gate に対する不正な ``approve`` / ``reject`` /
   ``cancel`` 呼び出しに対する Fail-Fast。
3. ``Final[Mapping]`` + :func:`types.MappingProxyType` により、pyright（再代入検出）
   と ランタイム（``setitem`` 拒否）の両方が import 後の変異を拒否する。遷移を追加
   したい将来の PR は *この* ファイルと対応するテストの両方を編集する必要がある。

下記 7 エントリは §確定 A ディスパッチ表の ``→`` セルと 1:1 対応する:

* ``PENDING`` → ``approve`` / ``reject`` / ``cancel``（決定を発行する 3 アクション、
  それぞれ APPROVED / REJECTED / CANCELLED に終端）。
* ``record_view`` は **すべての** decision 値（PENDING、APPROVED、REJECTED、
  CANCELLED）で自己ループする — 決定済み Gate の監査は正当な操作（§確定 G
  「誰がいつ何度見たか」）。4 つの自己ループは明示的に列挙し、テスト側がディスパッチ
  表をミラーできるようにし、将来の PR が ``record_view`` を一部の状態にサイレント
  に制限できないようにする。

残り 9 個の違法セル（PENDING 限定アクションを非 PENDING Gate に対して呼び出す）は
ルックアップで ``KeyError`` に当たり、Aggregate 境界で ``decision_already_decided``
（MSG-GT-001）に翻訳される。

``action`` は :data:`GateAction` で型レベルに制約されているため、タイプミス
（``'approv'`` 等）は実行前に pyright strict が捕捉する。4 個の ``Literal`` 値は
4 個の :class:`ExternalReviewGate` メソッドと 1:1 で対応する — このリストを更新せず
にメソッドを追加（あるいはその逆）するのは型エラーになる。
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final, Literal

from bakufu.domain.value_objects import ReviewDecision

type GateAction = Literal[
    "approve",
    "reject",
    "cancel",
    "record_view",
]
""":class:`ExternalReviewGate` のメソッド名と 1:1 対応するアクション名のクローズド集合。

§確定 A（task #42 §確定 A-2 パターン継承）に従い、Gate メソッドはランタイム値で
**ディスパッチしない**。各メソッドは
``state_machine.lookup(self.decision, '<method_name>')`` を呼び出し、アクション名は
コンパイル時の文字列リテラルとなる — テーブル ルックアップ結果とメソッドの振る舞い
が静的に紐付く。
"""


_TRANSITIONS: Mapping[tuple[ReviewDecision, GateAction], ReviewDecision] = MappingProxyType(
    {
        # PENDING — 決定を発行する 3 つの遷移と record_view 自己ループ。
        # approve / reject / cancel のいずれかの後、Gate はその 3 アクションについて
        # 終端となる。
        (ReviewDecision.PENDING, "approve"): ReviewDecision.APPROVED,
        (ReviewDecision.PENDING, "reject"): ReviewDecision.REJECTED,
        (ReviewDecision.PENDING, "cancel"): ReviewDecision.CANCELLED,
        (ReviewDecision.PENDING, "record_view"): ReviewDecision.PENDING,
        # APPROVED / REJECTED / CANCELLED — ``record_view`` のみ合法。Gate の監査
        # 証跡は遅れて読みに来た者を引き続き追跡できる。4 つの自己ループは推論
        # ではなく列挙する — ディスパッチ表が実装と完全に一致するよう
        # （§確定 A §「4 行明示列挙する根拠」）。
        (ReviewDecision.APPROVED, "record_view"): ReviewDecision.APPROVED,
        (ReviewDecision.REJECTED, "record_view"): ReviewDecision.REJECTED,
        (ReviewDecision.CANCELLED, "record_view"): ReviewDecision.CANCELLED,
    }
)
"""正準 7 エントリ遷移マップへの読み取り専用ビュー。

基底の ``dict`` を :class:`types.MappingProxyType` で包むことで、誰かがテーブルを
`cast` した場合でも ``_TRANSITIONS[k] = v`` がランタイムで ``TypeError`` になる。
``Final`` は pyright strict モードでシンボル自体の再代入をブロックする。
"""

TRANSITIONS: Final[Mapping[tuple[ReviewDecision, GateAction], ReviewDecision]] = _TRANSITIONS
"""遷移テーブルのパブリック エイリアス。

テストはこれを import してテーブル サイズ（``len(TRANSITIONS) == 7``）をアサート
し、``lookup`` を経由せずに全合法遷移を巡回する。:class:`MappingProxyType` ラッパは
依然として有効なので、import したコードもこれを変異できない。
"""


def lookup(current_decision: ReviewDecision, action: GateAction) -> ReviewDecision:
    """``(current_decision, action)`` に対する許可された ``next_decision`` を返す。

    Raises:
        KeyError: 対が正準遷移テーブルに存在しない場合。
            :class:`ExternalReviewGate` Aggregate がこれを捕捉し、診断のために元の／
            試行された decision を付与した
            :class:`ExternalReviewGateInvariantViolation(kind='decision_already_decided')`
            として再送出する — その変換は ``gate.py`` に置き、本モジュールを例外
            パッケージの import サイクルから解放する。
    """
    return _TRANSITIONS[(current_decision, action)]


def allowed_actions_from(current_decision: ReviewDecision) -> list[GateAction]:
    """``current_decision`` から合法なアクション部分集合を返す。

    :class:`ExternalReviewGate` が MSG-GT-001 の ``allowed_actions`` フィールドを
    埋めるために使う。これにより人間可読な next-action ヒントが *どの* 遷移であれば
    成功したかを表面化する。挿入順を保つ Python 3.7+ dict iteration を使うため、
    テスト スナップショットも決定的に保たれる。
    """
    return [action for (decision, action) in _TRANSITIONS if decision == current_decision]


__all__ = [
    "TRANSITIONS",
    "GateAction",
    "allowed_actions_from",
    "lookup",
]
