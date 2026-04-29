"""``BAKUFU_DATA_DIR`` の解決と絶対パスの強制。

データディレクトリは bakufu が管理するすべての永続成果物の真の出所
（ground truth）である: SQLite DB ファイル、WAL / SHM、構造化ログ、
``attachments/`` ストレージ、``bakufu_pid_registry`` 関連ファイル。

解決ポリシー
-----------
1. 環境変数 ``BAKUFU_DATA_DIR`` が設定されていればそれを使用する。
   - 相対パス、NUL バイト、``..`` セグメントは拒否する。これらは
     代表的なパストラバーサル攻撃ベクタであり、M1 ``SkillRef`` の
     防御パターン（H1〜H10）を本層でも再適用する。
2. 未設定の場合は OS の慣習的な配置に従う:
   - Linux/macOS: ``${XDG_DATA_HOME:-$HOME/.local/share}/bakufu``
   - Windows: ``%LOCALAPPDATA%\\bakufu``
3. シンボリックリンクは ``Path.resolve`` で解決し、下流コードが絶対
   パスの意味を再確認しなくて済むようにする。

解決済みパスはモジュールレベルでキャッシュされるため、以降の
``resolve()`` 呼び出しは O(1) となる。各 Bootstrap Stage は I/O 反復を
気にせず resolver を呼び出せる。
"""

from __future__ import annotations

import os
import platform
from pathlib import Path

from bakufu.infrastructure.exceptions import BakufuConfigError

ENV_VAR_NAME: str = "BAKUFU_DATA_DIR"

_resolved: Path | None = None


def resolve() -> Path:
    """シンボリックリンク解決済みの絶対データディレクトリを返す。

    キャッシュ動作: 初回呼び出しで環境変数 / OS デフォルトを検証し、
    以降の呼び出しは同じ :class:`Path` を返す。テストセットアップで
    再解決を強制する場合は :func:`reset` を使用する。

    Raises:
        BakufuConfigError: ``msg_id='MSG-PF-001'``。環境変数値が不正
            （相対パス、NUL バイト、``..`` セグメント、HOME が読めない）
            の場合。Bootstrap は非ゼロ終了する。
    """
    global _resolved
    if _resolved is not None:
        return _resolved

    raw = os.environ.get(ENV_VAR_NAME)
    path = _default_for_os() if raw is None or raw == "" else _validate_absolute(raw)

    # シンボリックリンクを一度だけ解決し、呼び出し側に正規化済みパスを
    # 返す。Bootstrap が後段でディレクトリを作成するため、この時点では
    # 未存在でも構わないので ``strict=False``。
    _resolved = path.resolve(strict=False)
    return _resolved


def reset() -> None:
    """シングルトンキャッシュをクリアする。テスト用ヘルパ。"""
    global _resolved
    _resolved = None


def _validate_absolute(value: str) -> Path:
    """相対パス、NUL バイト、トラバーサル列を拒否する。"""
    home_safe_value = value.replace(str(Path("~").expanduser()), "<HOME>", 1)
    if "\x00" in value:
        raise BakufuConfigError(
            msg_id="MSG-PF-001",
            message=(
                f"[FAIL] BAKUFU_DATA_DIR must be an absolute path "
                f"(got: {home_safe_value!r}; contains NUL byte)"
            ),
        )
    if ".." in Path(value).parts:
        raise BakufuConfigError(
            msg_id="MSG-PF-001",
            message=(
                f"[FAIL] BAKUFU_DATA_DIR must be an absolute path "
                f"(got: {home_safe_value}; contains '..' segment)"
            ),
        )
    path = Path(value)
    if not path.is_absolute():
        raise BakufuConfigError(
            msg_id="MSG-PF-001",
            message=(f"[FAIL] BAKUFU_DATA_DIR must be an absolute path (got: {home_safe_value})"),
        )
    return path


def _default_for_os() -> Path:
    """``BAKUFU_DATA_DIR`` の OS 別デフォルト配置。"""
    if platform.system() == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            raise BakufuConfigError(
                msg_id="MSG-PF-001",
                message=(
                    "[FAIL] BAKUFU_DATA_DIR must be an absolute path "
                    "(LOCALAPPDATA not set on Windows)"
                ),
            )
        return Path(local_app_data) / "bakufu"

    # POSIX 系: XDG_DATA_HOME があれば優先、なければ
    # ``$HOME/.local/share`` を採用する。
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "bakufu"
    home = os.environ.get("HOME")
    if not home:
        raise BakufuConfigError(
            msg_id="MSG-PF-001",
            message=(
                "[FAIL] BAKUFU_DATA_DIR must be an absolute path "
                "(HOME not set; cannot derive default)"
            ),
        )
    return Path(home) / ".local" / "share" / "bakufu"


__all__ = [
    "ENV_VAR_NAME",
    "reset",
    "resolve",
]
