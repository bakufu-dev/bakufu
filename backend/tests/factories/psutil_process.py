"""pid_gc テスト下の psutil.Process 挙動のためのファクトリ群.

``docs/features/persistence-foundation/test-design.md`` §外部 I/O 依存マップ
準拠。pid_gc のユニットテストは実プロセスの spawn / SIGKILL を行えない
(OS 依存で CI では危険) ため、psutil の文書化された契約と同じ
``create_time`` / ``children`` / ``is_running`` / ``send_signal`` 形状を
持つ最小限のモックオブジェクトを構築する。

各ファクトリは出力に ``_meta = {"synthetic": True}`` を付ける ── レビュアや
将来のリンタが、実 ``psutil.Process`` インスタンスとテスト由来オブジェクトを
区別できるように。

モック面は :mod:`pid_gc` が実際に呼ぶメソッドだけを意図的に反映する ──
それ以上を追加するとテストが本番コード経路から離れ過ぎる。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import psutil

if TYPE_CHECKING:
    from collections.abc import Sequence


def _tag_synthetic(mock_obj: MagicMock) -> MagicMock:
    """``_meta.synthetic=True`` を付け、レビュアがファクトリ出力を見分けられるようにする。"""
    mock_obj._meta = {"synthetic": True}  # 意図的なモック属性
    return mock_obj


def make_orphan_process(
    *,
    pid: int = 1234,
    create_time_seconds: float | None = None,
    children: Sequence[MagicMock] | None = None,
) -> MagicMock:
    """kill 対象のオーファンを表す psutil.Process モックを構築する。

    ``create_time()`` 値は記録済みの ``started_at`` と一致する ──
    pid_gc の分類器がこの形状に対して ``'orphan_kill'`` を返す。
    """
    proc = MagicMock(spec=psutil.Process)
    proc.pid = pid
    if create_time_seconds is None:
        create_time_seconds = datetime.now(UTC).timestamp() - 60.0
    proc.create_time.return_value = create_time_seconds
    proc.children.return_value = list(children) if children else []
    proc.send_signal = MagicMock()
    proc.is_running = MagicMock(return_value=False)
    return _tag_synthetic(proc)


def make_protected_process(
    *,
    pid: int = 5678,
    recorded_started_at: datetime | None = None,
) -> MagicMock:
    """``create_time`` が不一致な psutil.Process モックを構築する。

    pid_gc はこれを ``'protected'`` (PID が無関係なプロセスで再利用)
    と分類し、シグナル送信を拒否しなければならない。
    """
    proc = MagicMock(spec=psutil.Process)
    proc.pid = pid
    if recorded_started_at is None:
        recorded_started_at = datetime.now(UTC)
    # 実 create_time は記録値より 1 時間後 ── 明らかに別プロセス。
    proc.create_time.return_value = recorded_started_at.timestamp() + 3600.0
    proc.children.return_value = []
    proc.send_signal = MagicMock()
    proc.is_running = MagicMock(return_value=True)
    return _tag_synthetic(proc)


def make_no_such_process_factory(pid: int = 9999) -> type[psutil.NoSuchProcess]:
    """``pid`` を事前束縛した ``psutil.NoSuchProcess`` コンストラクタを返す。"""
    return type("_BoundNoSuchProcess", (psutil.NoSuchProcess,), {"_meta_pid": pid})


def make_access_denied_process(*, pid: int = 7777) -> MagicMock:
    """``create_time`` が ``psutil.AccessDenied`` を発するモックを構築する。

    pid_gc は WARN ログを出して次の sweep までレジストリ行を残さねばならない ──
    AccessDenied 配下で DELETE すると、オーファンが永遠に積み上がってしまう。
    """
    proc = MagicMock(spec=psutil.Process)
    proc.pid = pid
    proc.create_time.side_effect = psutil.AccessDenied(pid)
    proc.children.return_value = []
    proc.send_signal = MagicMock()
    proc.is_running = MagicMock(return_value=True)
    return _tag_synthetic(proc)


def make_child_process(*, pid: int) -> MagicMock:
    """descendants() 出力用に子 psutil.Process モックを構築する。"""
    child = MagicMock(spec=psutil.Process)
    child.pid = pid
    child.send_signal = MagicMock()
    child.is_running = MagicMock(return_value=False)
    return _tag_synthetic(child)


__all__ = [
    "make_access_denied_process",
    "make_child_process",
    "make_no_such_process_factory",
    "make_orphan_process",
    "make_protected_process",
]
