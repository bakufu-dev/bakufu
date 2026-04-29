""":class:`Task` Aggregate のための decision-table state machine。

``docs/features/task/detailed-design.md`` §確定 B（state machine テーブル ロック）
および §確定 A-2（Method x current_status -> action 名 のディスパッチ表）を実装する。
コントラクトは意図的に **フラットな ``Mapping[(TaskStatus, str), TaskStatus]``** で
あり、``if-elif`` 階段ではない。理由:

1. 許可遷移の集合がきっちり **1 つの構造で列挙可能** — コードレビュー時に
   §確定 A-2 の 60 セル ディスパッチ表と一目で照合できる。
2. ルックアップ関数は未知の ``(status, action)`` 対を ``KeyError`` で拒否するため、
   呼び元（``Task.<method>``）は失敗を
   :class:`TaskInvariantViolation(kind='state_transition_invalid')` で包む — 不正な
   state-machine バイパス試行への Fail-Fast。
3. ``Final[Mapping]`` + :func:`types.MappingProxyType` により、pyright（再代入検出）
   と ランタイム（``setitem`` 拒否）の両方が import 後の変異を拒否する。遷移を追加
   したい将来の PR は *この* ファイルと対応するテストの両方を編集する必要があり、
   設計の「物理的ロック」意図と一致する。

下記 13 エントリは §確定 A-2 ディスパッチ表の ``→`` セルと 1:1 対応する:

* ``PENDING``        — assign / cancel
* ``IN_PROGRESS``    — commit_deliverable / request_external_review /
                       advance_to_next / complete / block / cancel
* ``AWAITING_EXTERNAL_REVIEW`` — approve_review / reject_review / cancel
* ``BLOCKED``        — unblock_retry / cancel
* ``DONE`` / ``CANCELLED`` — 終端、**エントリ無し**（60 - 13 = 47 違法セルのうち、
                              DONE/CANCELLED の 20 は terminal_violation ゲートで
                              先に捕捉。残り 27 が ``state_transition_invalid``
                              に当たる）。

``action`` は :data:`TaskAction` で型レベルに制約されているため、タイプミス
（``'aproove_review'`` 等）は実行前に pyright strict が捕捉する。10 個の ``Literal``
値は 10 個の Task メソッドと 1:1 で対応する — このリストを更新せずにメソッドを追加
（あるいはその逆）するのは型エラーになる。
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final, Literal

from bakufu.domain.value_objects import TaskStatus

type TaskAction = Literal[
    "assign",
    "commit_deliverable",
    "request_external_review",
    "approve_review",
    "reject_review",
    "advance_to_next",
    "complete",
    "block",
    "unblock_retry",
    "cancel",
]
""":class:`Task` のメソッド名と 1:1 対応するアクション名のクローズド集合。

§確定 A-2（Steve R2 凍結）に従い、Task メソッドはランタイム値で **ディスパッチしない**。
各メソッドは ``state_machine.lookup(self.status, '<method_name>')`` を呼び出し、
アクション名はコンパイル時の文字列リテラルとなる — テーブル ルックアップ結果と
メソッドの振る舞いが静的に紐付く。
"""


_TRANSITIONS: Mapping[tuple[TaskStatus, TaskAction], TaskStatus] = MappingProxyType(
    {
        # PENDING — ``assign`` / ``cancel`` のみ到達可能。
        (TaskStatus.PENDING, "assign"): TaskStatus.IN_PROGRESS,
        (TaskStatus.PENDING, "cancel"): TaskStatus.CANCELLED,
        # IN_PROGRESS — 6 つの正規アクション。``deliverables`` / ``current_stage_id``
        # を更新しつつ status を変えない 2 つの自己ループ
        # （``commit_deliverable`` / ``advance_to_next``）を含む。
        (TaskStatus.IN_PROGRESS, "commit_deliverable"): TaskStatus.IN_PROGRESS,
        (TaskStatus.IN_PROGRESS, "request_external_review"): TaskStatus.AWAITING_EXTERNAL_REVIEW,
        (TaskStatus.IN_PROGRESS, "advance_to_next"): TaskStatus.IN_PROGRESS,
        (TaskStatus.IN_PROGRESS, "complete"): TaskStatus.DONE,
        (TaskStatus.IN_PROGRESS, "block"): TaskStatus.BLOCKED,
        (TaskStatus.IN_PROGRESS, "cancel"): TaskStatus.CANCELLED,
        # AWAITING_EXTERNAL_REVIEW — Gate 判定ディスパッチはアプリケーション側。
        # 2 つの専用メソッドは古い単一の ``advance`` メソッドを置き換える
        # （§確定 A-2 採用 (B)）。これにより Task は境界を越えて
        # ``ReviewDecision`` Aggregate VO に対して無知のままで済む。
        (TaskStatus.AWAITING_EXTERNAL_REVIEW, "approve_review"): TaskStatus.IN_PROGRESS,
        (TaskStatus.AWAITING_EXTERNAL_REVIEW, "reject_review"): TaskStatus.IN_PROGRESS,
        (TaskStatus.AWAITING_EXTERNAL_REVIEW, "cancel"): TaskStatus.CANCELLED,
        # BLOCKED — retry / cancel のみがライフサイクルを再開する。
        (TaskStatus.BLOCKED, "unblock_retry"): TaskStatus.IN_PROGRESS,
        (TaskStatus.BLOCKED, "cancel"): TaskStatus.CANCELLED,
    }
)
"""正準 13 エントリ遷移マップへの読み取り専用ビュー。

基底の ``dict`` を :class:`types.MappingProxyType` で包むことで、誰かがテーブルを
`cast` した場合でも ``_TRANSITIONS[k] = v`` がランタイムで ``TypeError`` になる。
``Final`` は pyright strict モードでシンボル自体の再代入をブロックする。両者あわせて
「import 後はテーブルが凍結される」コントラクトを端から端まで強制する。
"""

TRANSITIONS: Final[Mapping[tuple[TaskStatus, TaskAction], TaskStatus]] = _TRANSITIONS
"""遷移テーブルのパブリック エイリアス。

テストはこれを import してテーブル サイズ（``len(TRANSITIONS) == 13``）をアサート
し、``lookup`` を経由せずに全合法遷移を巡回する。:class:`MappingProxyType` ラッパは
依然として有効なので、import したコードもこれを変異できない。
"""


def lookup(current_status: TaskStatus, action: TaskAction) -> TaskStatus:
    """``(current_status, action)`` に対する許可された ``next_status`` を返す。

    Raises:
        KeyError: 対が正準遷移テーブルに存在しない場合。:class:`Task` Aggregate が
            これを捕捉し、診断のために ``allowed_actions`` リストを付与した
            :class:`TaskInvariantViolation(kind='state_transition_invalid')` として
            再送出する — その変換は ``task.py`` に置き、本モジュールを例外パッケージ
            の import サイクルから解放する。
    """
    return _TRANSITIONS[(current_status, action)]


def allowed_actions_from(current_status: TaskStatus) -> list[TaskAction]:
    """``current_status`` から合法なアクション部分集合を返す。

    :class:`Task` が MSG-TS-002 の ``allowed_actions`` フィールドを埋めるために
    使う。これにより人間可読な next-action ヒントが *どの* 遷移であれば成功した
    かを表面化する。挿入順を保つ Python 3.7+ dict iteration を使うため、テスト
    スナップショットも決定的に保たれる。
    """
    return [action for (status, action) in _TRANSITIONS if status == current_status]


__all__ = [
    "TRANSITIONS",
    "TaskAction",
    "allowed_actions_from",
    "lookup",
]
