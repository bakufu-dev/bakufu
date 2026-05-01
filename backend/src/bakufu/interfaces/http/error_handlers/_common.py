"""error_handlers 内部共有モジュール。

定数・ヘルパ関数・正規表現パターンを 1 箇所に集約する。
各ハンドラファイルはこのモジュールからインポートして使用する。
"""

from __future__ import annotations

import re
from typing import Final

from fastapi.responses import JSONResponse

from bakufu.interfaces.http.schemas.common import ErrorDetail, ErrorResponse

# ── 確定 A: エラーコード定数 ────────────────────────────────────────────────
NOT_FOUND: Final[str] = "not_found"
VALIDATION_ERROR: Final[str] = "validation_error"
INTERNAL_ERROR: Final[str] = "internal_error"
FORBIDDEN: Final[str] = "forbidden"
CONFLICT: Final[str] = "conflict"

# 確定 C: domain メッセージ前処理パターン (凍結)
# [FAIL] プレフィックスと \nNext:... を除去して domain 内部フォーマットを隠蔽する
_FAIL_PREFIX_RE: Final = re.compile(r"^\[FAIL\]\s*")


def error_response(code: str, message: str, status_code: int) -> JSONResponse:
    """統一フォーマットの ErrorResponse を JSON で返す。"""
    body = ErrorResponse(error=ErrorDetail(code=code, message=message))
    return JSONResponse(content=body.model_dump(), status_code=status_code)


def clean_domain_message(raw: str) -> str:
    """domain 例外メッセージから内部フォーマットを除去する。

    前処理ルール (確定 C 凍結):
    1. ``[FAIL] `` プレフィックスを除去
    2. ``\\nNext:`` 以降を除去して domain 内部フォーマットを隠蔽する

    Args:
        raw: domain 例外の ``str(exc)`` 文字列。

    Returns:
        クリーニング済みのメッセージ文字列。
    """
    return _FAIL_PREFIX_RE.sub("", raw).split("\nNext:")[0].strip()
