"""SkillRef.path のトラバーサル防御（Agent feature §確定 H, H1〜H10）。

各 Hx チェックは **モジュールレベルの純粋関数** として実装する。理由は以下:

1. テストから ``import`` して直接呼べるため、各ルールが独立して機能することを
   個別に検証できる（Workflow の :mod:`bakufu.domain.workflow.dag_validators` と
   同じテスタビリティ パターン — Confirmation F）。
2. :func:`_validate_skill_path` は 10 個のチェックの薄いシーケンサとして留まり、
   実行順序は設計ドキュメントによりロックされる。
3. 将来 ``feature/skill-loader`` Phase-2 でランタイム I/O 再チェックを追加する
   際、同じヘルパを再利用できる — パスポリシーの単一情報源。ルールの揺らぎが起きない。

これらの関数は :class:`AgentInvariantViolation` を直接送出する。これにより呼び元
（``SkillRef`` フィールド バリデータ）は、Pydantic の ``ValidationError`` ラッピング
を経由せずに構造化された ``kind='skill_path_invalid'`` 識別子を受け取れる。
"""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path, PurePosixPath

from bakufu.domain.exceptions import AgentInvariantViolation

# H2: 1〜500 文字（NFC 正規化後の長さ）。
MIN_PATH_LENGTH: int = 1
MAX_PATH_LENGTH: int = 500

# H7: 必須のプレフィックス セグメント。bakufu-data/skills/* 配下にないものは
# ファイル システムの状態にかかわらず VO 境界で拒否する。
REQUIRED_PARTS_PREFIX: tuple[str, str] = ("bakufu-data", "skills")
SKILLS_SUBDIR: str = "skills"

# H4: 先頭文字による拒否。
_WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")

# H9: Windows 予約デバイス名。拡張子を除いた part stem に対して
# 大文字小文字を無視して比較するため、"CON.md" も拒否される。
_WINDOWS_RESERVED_NAMES: frozenset[str] = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
)

# H3: 禁止文字 — NUL、ASCII C0/C1 制御文字、バックスラッシュ。
_ASCII_CONTROL_RANGE = frozenset(chr(c) for c in range(0x00, 0x20)) | {chr(0x7F)}
_FORBIDDEN_CHARS: frozenset[str] = _ASCII_CONTROL_RANGE | {"\\"}


def _violation(check_id: str, detail_extra: dict[str, object]) -> AgentInvariantViolation:
    """各 Hx ヘルパが共通で使う ``AgentInvariantViolation`` 形状を集約する。

    メッセージ書式と ``kind`` を一貫させるため、呼び元は文字列をパースせずに
    ``detail['check']`` で失敗箇所を特定できる。
    """
    detail = {"check": check_id, **detail_extra}
    return AgentInvariantViolation(
        kind="skill_path_invalid",
        message=f"[FAIL] SkillRef.path validation failed (check {check_id}): {detail}",
        detail=detail,
    )


# ---------------------------------------------------------------------------
# H1: NFC 正規化
# ---------------------------------------------------------------------------
def _h1_nfc_normalize(raw_path: str) -> str:
    """NFC を適用する。返却された文字列が以降のヘルパが検査する対象となる。"""
    return unicodedata.normalize("NFC", raw_path)


# ---------------------------------------------------------------------------
# H2: 長さ 1〜500
# ---------------------------------------------------------------------------
def _h2_check_length(path: str) -> None:
    length = len(path)
    if not (MIN_PATH_LENGTH <= length <= MAX_PATH_LENGTH):
        raise _violation(
            "H2",
            {
                "length": length,
                "min": MIN_PATH_LENGTH,
                "max": MAX_PATH_LENGTH,
            },
        )


# ---------------------------------------------------------------------------
# H3: 禁止文字（NUL / 制御文字 / バックスラッシュ）
# ---------------------------------------------------------------------------
def _h3_check_forbidden_chars(path: str) -> None:
    for ch in path:
        if ch in _FORBIDDEN_CHARS:
            raise _violation("H3", {"forbidden_char_codepoint": ord(ch)})


# ---------------------------------------------------------------------------
# H4: 先頭文字の拒否（POSIX 絶対 / Windows 絶対 / ホームのチルダ）
# ---------------------------------------------------------------------------
def _h4_check_leading(path: str) -> None:
    if path.startswith("/"):
        raise _violation("H4", {"reason": "leading slash (POSIX absolute)"})
    if path.startswith("~"):
        raise _violation("H4", {"reason": "leading tilde (home expansion)"})
    if _WINDOWS_ABSOLUTE_RE.match(path):
        raise _violation("H4", {"reason": "Windows absolute path"})


# ---------------------------------------------------------------------------
# H5: トラバーサル列と前後の空白
# ---------------------------------------------------------------------------
def _h5_check_traversal_sequences(path: str) -> None:
    if path != path.strip():
        raise _violation("H5", {"reason": "leading or trailing whitespace"})
    # ``path == '.'`` / ``path == '..'`` / 先頭の ``./`` や ``../`` は、
    # PurePosixPath を通すとサイレントに往復してしまうカレント／親ディレクトリ
    # エイリアスとなる。この層で明示的に拒否する。
    if path in {".", ".."} or path.startswith(("./", "../")):
        raise _violation("H5", {"reason": "path starts with '.' or '..'"})
    if path.endswith(("/.", "/..", "/")):
        raise _violation("H5", {"reason": "path ends with '.' or '..' or trailing slash"})
    # 任意の位置に出現する `..` トラバーサル — 最も一般的な攻撃形態。
    if ".." in path.split("/"):
        raise _violation("H5", {"reason": "'..' parent-dir traversal in path"})


# ---------------------------------------------------------------------------
# H6: PurePosixPath でパースして parts を返す
# ---------------------------------------------------------------------------
def _h6_parse_parts(path: str) -> tuple[str, ...]:
    return PurePosixPath(path).parts


# ---------------------------------------------------------------------------
# H7: プレフィックスは ('bakufu-data', 'skills', <rest>) でなければならない
# ---------------------------------------------------------------------------
def _h7_check_prefix(parts: tuple[str, ...]) -> None:
    if len(parts) < 3:
        raise _violation(
            "H7",
            {"reason": "path needs at least 3 components", "parts_count": len(parts)},
        )
    if parts[0] != REQUIRED_PARTS_PREFIX[0] or parts[1] != REQUIRED_PARTS_PREFIX[1]:
        raise _violation(
            "H7",
            {
                "reason": "prefix must be 'bakufu-data/skills/'",
                "actual_prefix": list(parts[:2]),
            },
        )


# ---------------------------------------------------------------------------
# H8: パース後の各 part を再度禁止文字でチェック（多層防御）
# ---------------------------------------------------------------------------
def _h8_recheck_parts(parts: tuple[str, ...]) -> None:
    for index, part in enumerate(parts):
        for ch in part:
            if ch in _FORBIDDEN_CHARS:
                raise _violation(
                    "H8",
                    {"part_index": index, "forbidden_char_codepoint": ord(ch)},
                )


# ---------------------------------------------------------------------------
# H9: Windows 予約名
# ---------------------------------------------------------------------------
def _h9_check_windows_reserved(parts: tuple[str, ...]) -> None:
    for index, part in enumerate(parts):
        # 比較のため拡張子を除いて stem を取得: "CON.md" → "CON"。
        stem = part.split(".", 1)[0].upper()
        if stem in _WINDOWS_RESERVED_NAMES:
            raise _violation(
                "H9",
                {
                    "part_index": index,
                    "reserved_name": stem,
                },
            )


# ---------------------------------------------------------------------------
# H10: ファイルシステム実体に基づく base-escape 検証
# ---------------------------------------------------------------------------
def _h10_check_base_escape(path: str) -> None:
    """``BAKUFU_DATA_DIR / path`` を resolve し、``BAKUFU_DATA_DIR / 'bakufu-data' / 'skills'``
    （正準 skills ルート）の配下にあることを要求する。

    相対パス ``bakufu-data/skills/<rest>`` は ``BAKUFU_DATA_DIR`` を起点として
    解決される。連結された絶対パスは skills ルートの配下に留まらなければならない。
    ``Path.resolve()`` はシンボリックリンクを辿るため、skills サブディレクトリ
    経由のシンボリックリンク エスケープも検出される — 最終的な防御ライン。
    ``BAKUFU_DATA_DIR`` 未設定の場合はサイレントにスキップせず、構造化された
    失敗を送出する（多層防御）。
    """
    base_dir_str = os.environ.get("BAKUFU_DATA_DIR")
    if not base_dir_str:
        raise _violation(
            "H10",
            {"reason": "BAKUFU_DATA_DIR not set"},
        )
    base_dir = Path(base_dir_str)
    # ``REQUIRED_PARTS_PREFIX`` は ``('bakufu-data', 'skills')`` であるため、
    # 正準 skills ルートはちょうどこのプレフィックスを環境変数の下に連結したもの。
    skills_root = base_dir.joinpath(*REQUIRED_PARTS_PREFIX).resolve()
    candidate = (base_dir / path).resolve()
    if not candidate.is_relative_to(skills_root):
        raise _violation(
            "H10",
            {
                "reason": "resolved path escapes BAKUFU_DATA_DIR/bakufu-data/skills/",
                "skills_root": str(skills_root),
            },
        )


# ---------------------------------------------------------------------------
# オーケストレータ（SkillRef.field_validator から使用）
# ---------------------------------------------------------------------------
def _validate_skill_path(raw_path: str) -> str:
    """設計でロックされた順序で H1〜H10 を実行し、NFC 正規化済みの形を返す。

    返り値は :class:`SkillRef` が ``path`` として保存する値である。呼び元は必ず
    入力をこの関数の出力で置き換えなければならない。これによりダウンストリーム
    の利用側に未正規化文字列が渡ることを防ぐ。

    Raises:
        AgentInvariantViolation: 失敗時に ``kind='skill_path_invalid'`` で送出。
            ``detail['check']`` には Hx 識別子（``'H1'`` ... ``'H10'``）が入り、
            HTTP / API 層はメッセージ文字列をパースせずに失敗箇所をローカライズ
            できる。
    """
    normalized = _h1_nfc_normalize(raw_path)
    _h2_check_length(normalized)
    _h3_check_forbidden_chars(normalized)
    _h4_check_leading(normalized)
    _h5_check_traversal_sequences(normalized)
    parts = _h6_parse_parts(normalized)
    _h7_check_prefix(parts)
    _h8_recheck_parts(parts)
    _h9_check_windows_reserved(parts)
    _h10_check_base_escape(normalized)
    return normalized


__all__ = [
    "MAX_PATH_LENGTH",
    "MIN_PATH_LENGTH",
    "REQUIRED_PARTS_PREFIX",
    "SKILLS_SUBDIR",
    "_h1_nfc_normalize",
    "_h2_check_length",
    "_h3_check_forbidden_chars",
    "_h4_check_leading",
    "_h5_check_traversal_sequences",
    "_h6_parse_parts",
    "_h7_check_prefix",
    "_h8_recheck_parts",
    "_h9_check_windows_reserved",
    "_h10_check_base_escape",
    "_validate_skill_path",
]
